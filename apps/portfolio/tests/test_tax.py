"""Tests for realized-gains / tax reporting (Stage 5, FIFO)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.portfolio.models import Asset, Portfolio, Transaction
from apps.portfolio.tax import realized_gains, realized_summary


def _asset(ticker="AAPL", currency="USD") -> Asset:
    return Asset.objects.create(
        ticker=ticker, asset_type="STOCK", market="US", currency=currency
    )


def _txn(pf, asset, kind, qty, price, fee="0", *, y=2024, m=1, d=1):
    return Transaction.objects.create(
        portfolio=pf, asset=asset, kind=kind,
        quantity=Decimal(qty), price=Decimal(price), fee=Decimal(fee),
        executed_at=datetime(y, m, d, tzinfo=UTC),
    )


@pytest.mark.django_db
def test_simple_realized_gain(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    a = _asset()
    _txn(pf, a, "BUY", "10", "100", d=1)
    _txn(pf, a, "SELL", "10", "150", d=2)

    lots = realized_gains(pf)
    assert len(lots) == 1
    lot = lots[0]
    assert lot.quantity == Decimal("10")
    assert lot.cost == Decimal("1000")
    assert lot.proceeds == Decimal("1500")
    assert lot.gain == Decimal("500")


@pytest.mark.django_db
def test_fees_reduce_gain(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    a = _asset()
    _txn(pf, a, "BUY", "10", "100", "10", d=1)   # cost 1010
    _txn(pf, a, "SELL", "10", "150", "10", d=2)  # proceeds 1490

    [lot] = realized_gains(pf)
    assert lot.cost == Decimal("1010")
    assert lot.proceeds == Decimal("1490")
    assert lot.gain == Decimal("480")


@pytest.mark.django_db
def test_fifo_matches_oldest_lots_first(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    a = _asset()
    _txn(pf, a, "BUY", "10", "100", d=1)   # lot1 cost 1000
    _txn(pf, a, "BUY", "10", "200", d=2)   # lot2 cost 2000
    _txn(pf, a, "SELL", "15", "250", d=3)  # proceeds 3750

    lots = realized_gains(pf)
    assert len(lots) == 2  # spans two buy lots
    # FIFO: first 10 from lot1, then 5 from lot2.
    assert lots[0].quantity == Decimal("10")
    assert lots[0].cost == Decimal("1000")
    assert lots[0].proceeds == Decimal("2500")
    assert lots[0].gain == Decimal("1500")
    assert lots[1].quantity == Decimal("5")
    assert lots[1].cost == Decimal("1000")  # 5 * 200
    assert lots[1].proceeds == Decimal("1250")
    assert lots[1].gain == Decimal("250")


@pytest.mark.django_db
def test_year_filter(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    a = _asset()
    _txn(pf, a, "BUY", "20", "100", y=2023, d=1)
    _txn(pf, a, "SELL", "10", "150", y=2023, m=6)
    _txn(pf, a, "SELL", "10", "200", y=2024, m=6)

    assert len(realized_gains(pf, year=2023)) == 1
    assert len(realized_gains(pf, year=2024)) == 1
    assert len(realized_gains(pf)) == 2


@pytest.mark.django_db
def test_holding_days(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    a = _asset()
    _txn(pf, a, "BUY", "10", "100", y=2024, m=1, d=1)
    _txn(pf, a, "SELL", "10", "150", y=2024, m=1, d=31)
    [lot] = realized_gains(pf)
    assert lot.holding_days == 30


@pytest.mark.django_db
def test_summary_groups_by_currency(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    us = _asset("AAPL", "USD")
    ru = _asset("SBER", "RUB")
    _txn(pf, us, "BUY", "10", "100", d=1)
    _txn(pf, us, "SELL", "10", "150", d=2)   # +500 USD
    _txn(pf, ru, "BUY", "10", "100", d=1)
    _txn(pf, ru, "SELL", "10", "90", d=2)    # -100 RUB

    summary = realized_summary(realized_gains(pf))
    assert summary["USD"]["gain"] == Decimal("500")
    assert summary["RUB"]["gain"] == Decimal("-100")


@pytest.mark.django_db
def test_no_sells_is_empty(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    a = _asset()
    _txn(pf, a, "BUY", "10", "100", d=1)
    assert realized_gains(pf) == []
    assert realized_summary([]) == {}
