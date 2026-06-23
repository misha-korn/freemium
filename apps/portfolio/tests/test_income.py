"""Dividend income service: history, summary, calendar, yield-on-cost (Tier 1)."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.portfolio.income import (
    dividend_calendar,
    dividend_history,
    dividend_summary,
    dividend_years,
    yield_on_cost,
)
from apps.portfolio.models import Asset, DividendPayment, Portfolio, Transaction


def _asset(ticker="AAPL", currency="USD", market="US") -> Asset:
    return Asset.objects.create(
        ticker=ticker, asset_type="STOCK", market=market, currency=currency
    )


def _dividend(portfolio, asset, *, amount, tax="0", paid_on, currency=None, kind="DIVIDEND"):
    return DividendPayment.objects.create(
        portfolio=portfolio,
        asset=asset,
        kind=kind,
        amount=Decimal(amount),
        tax_withheld=Decimal(tax),
        currency=currency or asset.currency,
        paid_on=paid_on,
    )


@pytest.mark.django_db
def test_net_amount_is_gross_minus_tax(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    payment = _dividend(pf, _asset(), amount="100", tax="13", paid_on=date(2024, 3, 1))

    assert payment.net_amount == Decimal("87")


@pytest.mark.django_db
def test_summary_groups_per_currency_and_never_mixes(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    usd = _asset("AAPL", "USD")
    rub = _asset("SBER", "RUB", market="MOEX")
    _dividend(pf, usd, amount="100", tax="15", paid_on=date(2024, 1, 10))
    _dividend(pf, usd, amount="50", tax="0", paid_on=date(2024, 6, 10))
    _dividend(pf, rub, amount="200", tax="26", paid_on=date(2024, 3, 10))

    summary = dividend_summary(dividend_history(pf))

    assert summary["USD"]["gross"] == Decimal("150")
    assert summary["USD"]["tax"] == Decimal("15")
    assert summary["USD"]["net"] == Decimal("135")
    assert summary["USD"]["count"] == 2
    assert summary["RUB"]["net"] == Decimal("174")
    # Currencies stay separate — no cross-currency total anywhere.
    assert set(summary.keys()) == {"USD", "RUB"}


@pytest.mark.django_db
def test_history_filters_by_year_newest_first(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    _dividend(pf, asset, amount="10", paid_on=date(2023, 5, 1))
    _dividend(pf, asset, amount="20", paid_on=date(2024, 2, 1))
    _dividend(pf, asset, amount="30", paid_on=date(2024, 9, 1))

    rows_2024 = dividend_history(pf, year=2024)

    assert [r.amount for r in rows_2024] == [Decimal("30"), Decimal("20")]
    assert dividend_years(pf) == [2024, 2023]


@pytest.mark.django_db
def test_calendar_groups_by_month_with_per_currency_net(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    usd = _asset("AAPL", "USD")
    rub = _asset("SBER", "RUB", market="MOEX")
    _dividend(pf, usd, amount="100", tax="10", paid_on=date(2024, 3, 5))
    _dividend(pf, rub, amount="200", tax="0", paid_on=date(2024, 3, 20))
    _dividend(pf, usd, amount="40", tax="0", paid_on=date(2024, 1, 15))

    calendar = dividend_calendar(dividend_history(pf))

    # Newest month first.
    assert [(g.year, g.month) for g in calendar] == [(2024, 3), (2024, 1)]
    march = calendar[0]
    assert march.net_by_currency == {"USD": Decimal("90"), "RUB": Decimal("200")}
    assert len(march.payments) == 2


@pytest.mark.django_db
def test_yield_on_cost_uses_open_position_basis(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset("AAPL", "USD")
    # Cost basis: 10 @ 100 + 0 fee = 1000 invested.
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    _dividend(pf, asset, amount="70", tax="0", paid_on=date(2024, 1, 1))

    summary = dividend_summary(dividend_history(pf))
    yoc = yield_on_cost(summary, {"USD": Decimal("1000")})

    assert yoc["USD"] == Decimal("0.07")  # 70 / 1000 == 7%


@pytest.mark.django_db
def test_yield_on_cost_is_none_without_basis(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _dividend(pf, _asset(), amount="50", paid_on=date(2024, 1, 1))

    summary = dividend_summary(dividend_history(pf))
    # No open position -> no cost basis in USD -> honest None, not a fake yield.
    assert yield_on_cost(summary, {})["USD"] is None
