"""Rebalancing: current vs target weights + buy/sell suggestions (Tier 2 #6)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.marketdata.models import PriceQuote
from apps.portfolio.models import Asset, Portfolio, RebalanceTarget, Transaction
from apps.portfolio.rebalance import build_rebalance


def _hold(pf, asset, qty, cost):
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal(qty),
        price=Decimal(cost), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


def _price(asset, price, currency="USD"):
    PriceQuote.objects.create(
        asset=asset, price=Decimal(price), currency=currency,
        as_of=datetime.now(UTC), source="TEST",
    )


def _two_asset_priced_portfolio(user):
    aapl = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    msft = Asset.objects.create(ticker="MSFT", asset_type="STOCK", market="US", currency="USD")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _hold(pf, aapl, "10", "120")
    _hold(pf, msft, "10", "90")
    _price(aapl, "150")   # market value 1500
    _price(msft, "100")   # market value 1000  -> total 2500
    return pf, aapl, msft


@pytest.mark.django_db
def test_suggests_buy_and_sell_to_reach_targets(user):
    pf, aapl, msft = _two_asset_priced_portfolio(user)
    RebalanceTarget.objects.create(portfolio=pf, asset=aapl, target_weight=Decimal("50"))
    RebalanceTarget.objects.create(portfolio=pf, asset=msft, target_weight=Decimal("50"))

    result = build_rebalance(pf)
    assert result["available"] is True
    assert result["total"] == Decimal("2500.00")
    rows = {r.asset.ticker: r for r in result["rows"]}

    # AAPL is overweight (60% vs 50%) -> sell 250; MSFT underweight -> buy 250.
    assert rows["AAPL"].current_weight == Decimal("0.6")
    assert rows["AAPL"].action == "SELL"
    assert rows["AAPL"].amount == Decimal("250.00")
    assert rows["MSFT"].action == "BUY"
    assert rows["MSFT"].amount == Decimal("250.00")


@pytest.mark.django_db
def test_on_target_holding_is_hold(user):
    pf, aapl, msft = _two_asset_priced_portfolio(user)
    # AAPL is exactly 60% of the portfolio.
    RebalanceTarget.objects.create(portfolio=pf, asset=aapl, target_weight=Decimal("60"))

    rows = {r.asset.ticker: r for r in build_rebalance(pf)["rows"]}
    assert rows["AAPL"].action == "HOLD"
    assert rows["AAPL"].amount == Decimal("0.00")


@pytest.mark.django_db
def test_target_for_unheld_asset_suggests_full_buy(user):
    pf, aapl, msft = _two_asset_priced_portfolio(user)
    voo = Asset.objects.create(ticker="VOO", asset_type="ETF", market="US", currency="USD")
    RebalanceTarget.objects.create(portfolio=pf, asset=voo, target_weight=Decimal("10"))

    rows = {r.asset.ticker: r for r in build_rebalance(pf)["rows"]}
    # 10% of 2500 = 250, nothing held yet -> buy 250.
    assert rows["VOO"].current_weight is None
    assert rows["VOO"].action == "BUY"
    assert rows["VOO"].amount == Decimal("250.00")


@pytest.mark.django_db
def test_unavailable_when_not_priced(user):
    aapl = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _hold(pf, aapl, "10", "120")  # no PriceQuote -> unpriced
    RebalanceTarget.objects.create(portfolio=pf, asset=aapl, target_weight=Decimal("100"))

    result = build_rebalance(pf)
    assert result["available"] is False
    assert result["total"] is None
    row = result["rows"][0]
    assert row.current_weight is None
    assert row.amount is None
    assert row.target_percent == Decimal("100")  # target still shown for editing


# --- view ------------------------------------------------------------------ #
@pytest.mark.django_db
def test_rebalance_page_requires_ownership(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:rebalance", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_post_saves_updates_and_removes_targets(auth_client, user):
    pf, aapl, msft = _two_asset_priced_portfolio(user)
    url = reverse("portfolio:rebalance", kwargs={"pk": pf.pk})

    # Set both targets.
    resp = auth_client.post(url, {f"target_{aapl.pk}": "50", f"target_{msft.pk}": "50"})
    assert resp.status_code == 302
    assert RebalanceTarget.objects.filter(portfolio=pf).count() == 2

    # Blank one out -> it's removed; the other updates.
    resp = auth_client.post(url, {f"target_{aapl.pk}": "70", f"target_{msft.pk}": ""})
    assert resp.status_code == 302
    assert RebalanceTarget.objects.filter(portfolio=pf, asset=msft).count() == 0
    assert RebalanceTarget.objects.get(portfolio=pf, asset=aapl).target_weight == Decimal("70")


@pytest.mark.django_db
def test_post_ignores_invalid_target(auth_client, user):
    pf, aapl, msft = _two_asset_priced_portfolio(user)
    url = reverse("portfolio:rebalance", kwargs={"pk": pf.pk})
    resp = auth_client.post(url, {f"target_{aapl.pk}": "abc", f"target_{msft.pk}": "-5"})
    assert resp.status_code == 302
    assert RebalanceTarget.objects.filter(portfolio=pf).count() == 0


@pytest.mark.django_db
def test_post_requires_ownership(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    url = reverse("portfolio:rebalance", kwargs={"pk": foreign.pk})
    assert auth_client.post(url, {}).status_code == 404
