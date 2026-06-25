"""Dividend history auto-import: as-of quantity, dedup, view (Tier 3 #9)."""
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.marketdata.models import AssetDividend
from apps.portfolio.dividend_import import import_dividends, quantity_as_of
from apps.portfolio.models import Asset, DividendPayment, Portfolio, Transaction


def _asset(ticker="AAPL", currency="USD", market="US", asset_type="STOCK"):
    return Asset.objects.create(
        ticker=ticker, asset_type=asset_type, market=market, currency=currency
    )


def _buy(pf, asset, qty, when):
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal(qty),
        price=Decimal("100"), fee=Decimal("0"), executed_at=when,
    )


def _dividend_record(asset, ex_date, amount, currency="USD"):
    return AssetDividend.objects.create(
        asset=asset, ex_date=ex_date, amount=Decimal(amount),
        currency=currency, source="TEST",
    )


# --- quantity_as_of -------------------------------------------------------- #
@pytest.mark.django_db
def test_quantity_as_of_counts_only_trades_before_date(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", datetime(2024, 1, 1, tzinfo=UTC))
    _buy(pf, asset, "5", datetime(2024, 6, 1, tzinfo=UTC))

    # Before an ex-date of 2024-03-01 only the first buy counts.
    assert quantity_as_of(pf, asset, date(2024, 3, 1)) == Decimal("10")
    assert quantity_as_of(pf, asset, date(2024, 7, 1)) == Decimal("15")
    # Before the first buy: nothing held.
    assert quantity_as_of(pf, asset, date(2023, 1, 1)) == Decimal("0")


# --- import_dividends ------------------------------------------------------ #
@pytest.mark.django_db
def test_import_creates_payments_from_records(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", datetime(2024, 1, 1, tzinfo=UTC))
    _dividend_record(asset, date(2024, 2, 9), "0.24")
    _dividend_record(asset, date(2024, 5, 10), "0.25")

    with patch("apps.portfolio.dividend_import.sync_dividends", return_value=0):
        result = import_dividends(pf)

    assert result["created"] == 2
    feb = DividendPayment.objects.get(portfolio=pf, paid_on=date(2024, 2, 9))
    assert feb.amount == Decimal("2.40")  # 0.24 * 10
    assert feb.currency == "USD"
    assert feb.note == "auto-import"


@pytest.mark.django_db
def test_import_skips_dividends_before_holding(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", datetime(2024, 3, 1, tzinfo=UTC))
    _dividend_record(asset, date(2024, 2, 9), "0.24")  # before the buy -> skipped
    _dividend_record(asset, date(2024, 5, 10), "0.25")  # after -> imported

    with patch("apps.portfolio.dividend_import.sync_dividends", return_value=0):
        result = import_dividends(pf)

    assert result["created"] == 1
    assert DividendPayment.objects.filter(portfolio=pf).count() == 1
    assert DividendPayment.objects.filter(paid_on=date(2024, 2, 9)).count() == 0


@pytest.mark.django_db
def test_import_is_idempotent(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", datetime(2024, 1, 1, tzinfo=UTC))
    _dividend_record(asset, date(2024, 5, 10), "0.25")

    with patch("apps.portfolio.dividend_import.sync_dividends", return_value=0):
        import_dividends(pf)
        result = import_dividends(pf)

    assert result["created"] == 0  # already imported, no duplicate
    assert DividendPayment.objects.filter(portfolio=pf).count() == 1


@pytest.mark.django_db
def test_import_captures_dividend_on_since_sold_position(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", datetime(2024, 1, 1, tzinfo=UTC))
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"), executed_at=datetime(2024, 6, 1, tzinfo=UTC),
    )  # sold everything in June
    _dividend_record(asset, date(2024, 3, 10), "0.50")  # held 10 in March

    with patch("apps.portfolio.dividend_import.sync_dividends", return_value=0):
        result = import_dividends(pf)

    assert result["created"] == 1  # captured even though now zero held
    assert DividendPayment.objects.get(portfolio=pf).amount == Decimal("5.00")


# --- view ------------------------------------------------------------------ #
@pytest.mark.django_db
def test_pull_dividends_view(auth_client, user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", datetime(2024, 1, 1, tzinfo=UTC))
    _dividend_record(asset, date(2024, 5, 10), "0.25")

    with patch("apps.portfolio.dividend_import.sync_dividends", return_value=0):
        resp = auth_client.post(reverse("portfolio:pull_dividends", kwargs={"pk": pf.pk}))

    assert resp.status_code == 302
    assert DividendPayment.objects.filter(portfolio=pf).count() == 1


@pytest.mark.django_db
def test_pull_dividends_requires_ownership(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    resp = auth_client.post(reverse("portfolio:pull_dividends", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404
