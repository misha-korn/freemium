"""Tests for the account-level overview shown on the portfolio list (Stage 3)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.marketdata.models import PriceQuote
from apps.portfolio.models import Asset, Portfolio, Transaction
from apps.portfolio.overview import build_account_overview


def _buy(portfolio: Portfolio, asset: Asset, qty: str, price: str) -> None:
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal(qty), price=Decimal(price), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


def _quote(asset: Asset, price: str, currency: str) -> None:
    PriceQuote.objects.create(
        asset=asset, price=Decimal(price), currency=currency,
        as_of=datetime.now(UTC), source="TEST",
    )


@pytest.mark.django_db
def test_overview_builds_one_card_per_portfolio(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf1 = Portfolio.objects.create(owner=user, name="A", base_currency="USD")
    pf2 = Portfolio.objects.create(owner=user, name="B", base_currency="USD")
    _buy(pf1, asset, "10", "100")
    _quote(asset, "150", "USD")

    overview = build_account_overview([pf1, pf2])

    assert [c.portfolio.name for c in overview["cards"]] == ["A", "B"]
    card_a = overview["cards"][0]
    assert card_a.market_value == Decimal("1500")
    assert card_a.invested == Decimal("1000")
    assert card_a.unrealised_pnl == Decimal("500")
    assert card_a.fully_priced is True


@pytest.mark.django_db
def test_overview_combines_totals_when_one_currency(user):
    a1 = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    a2 = Asset.objects.create(ticker="MSFT", asset_type="STOCK", market="US", currency="USD")
    pf1 = Portfolio.objects.create(owner=user, name="A", base_currency="USD")
    pf2 = Portfolio.objects.create(owner=user, name="B", base_currency="USD")
    _buy(pf1, a1, "10", "100")  # invested 1000 -> mv 1500
    _quote(a1, "150", "USD")
    _buy(pf2, a2, "10", "100")  # invested 1000 -> mv 2000
    _quote(a2, "200", "USD")

    combined = build_account_overview([pf1, pf2])["combined"]

    assert combined is not None
    assert combined["currency"] == "USD"
    assert combined["invested"] == Decimal("2000")
    assert combined["market_value"] == Decimal("3500")
    assert combined["unrealised_pnl"] == Decimal("1500")
    assert combined["simple_return"] == Decimal("0.75")
    assert combined["portfolio_count"] == 2


@pytest.mark.django_db
def test_overview_no_combined_total_for_mixed_currencies(user):
    us = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    ru = Asset.objects.create(ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB")
    pf_usd = Portfolio.objects.create(owner=user, name="US", base_currency="USD")
    pf_rub = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    _buy(pf_usd, us, "10", "100")
    _buy(pf_rub, ru, "10", "100")

    overview = build_account_overview([pf_usd, pf_rub])

    # Two cards, but no combined total — we never mix currencies without FX.
    assert len(overview["cards"]) == 2
    assert overview["combined"] is None


@pytest.mark.django_db
def test_overview_combined_market_value_none_when_a_portfolio_unpriced(user):
    a1 = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    a2 = Asset.objects.create(ticker="MSFT", asset_type="STOCK", market="US", currency="USD")
    pf1 = Portfolio.objects.create(owner=user, name="A", base_currency="USD")
    pf2 = Portfolio.objects.create(owner=user, name="B", base_currency="USD")
    _buy(pf1, a1, "10", "100")
    _quote(a1, "150", "USD")
    _buy(pf2, a2, "10", "100")  # no quote -> unpriced

    combined = build_account_overview([pf1, pf2])["combined"]

    # Cost basis still sums; market value cannot (one side unpriced).
    assert combined["invested"] == Decimal("2000")
    assert combined["market_value"] is None
    assert combined["unrealised_pnl"] is None


@pytest.mark.django_db
def test_overview_empty():
    overview = build_account_overview([])
    assert overview["cards"] == []
    assert overview["combined"] is None
