"""Stock dividend estimate + forecast integration (Tier 3 #9, estimate)."""
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.marketdata.models import AssetDividend
from apps.portfolio import dividend_estimate
from apps.portfolio.forecast import income_forecast
from apps.portfolio.models import Asset, Portfolio, Transaction


def _rec(ex_date, amount, currency="RUB"):
    return SimpleNamespace(ex_date=ex_date, amount=Decimal(amount), currency=currency)


_QUARTERLY = [
    _rec(date(2023, 9, 15), "10"),
    _rec(date(2023, 12, 15), "10"),
    _rec(date(2024, 3, 15), "10"),
    _rec(date(2024, 6, 15), "10"),
]


# --- pure logic ------------------------------------------------------------ #
def test_infer_period_quarterly():
    assert dividend_estimate.infer_period_months([r.ex_date for r in _QUARTERLY]) == 3


def test_infer_period_annual():
    dates = [date(2022, 5, 1), date(2023, 5, 1), date(2024, 5, 1)]
    assert dividend_estimate.infer_period_months(dates) == 12


def test_infer_period_none_for_single_point():
    assert dividend_estimate.infer_period_months([date(2024, 1, 1)]) is None


def test_estimate_upcoming_projects_quarterly():
    out = dividend_estimate.estimate_upcoming(
        _QUARTERLY, Decimal("100"), date(2024, 7, 1), date(2025, 7, 1)
    )
    # From 2024-06-15 step +3m: Sep, Dec 2024, Mar, Jun 2025 -> 4 estimates.
    assert [e["date"] for e in out] == [
        date(2024, 9, 15), date(2024, 12, 15), date(2025, 3, 15), date(2025, 6, 15)
    ]
    assert all(e["amount"] == Decimal("1000.00") for e in out)  # 10 * 100


def test_estimate_empty_with_one_record():
    one = [_rec(date(2024, 6, 15), "10")]
    assert dividend_estimate.estimate_upcoming(one, Decimal("100"), date(2024, 7, 1), date(2025, 7, 1)) == []


def test_trailing_annual_sums_last_12_months():
    annual = dividend_estimate.trailing_annual_per_share(_QUARTERLY, date(2024, 7, 1))
    assert annual == Decimal("40")  # 4 × 10 in the trailing year


# --- forecast integration -------------------------------------------------- #
@pytest.mark.django_db
def test_forecast_includes_estimated_dividends_and_yield(user):
    asset = Asset.objects.create(ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("100"),
        price=Decimal("250"), fee=Decimal("0"), executed_at=datetime(2023, 1, 1, tzinfo=UTC),
    )  # cost basis 25000
    for r in _QUARTERLY:
        AssetDividend.objects.create(
            asset=asset, ex_date=r.ex_date, amount=r.amount, currency="RUB", source="TEST"
        )

    result = income_forecast(pf, months=12, as_of=date(2024, 7, 1))

    assert result["has_estimates"] is True
    # Trailing 12m: 4 × 10 × 100 = 4000; yield-on-cost = 4000 / 25000 = 0.16.
    assert result["annual_dividends"]["RUB"]["amount"] == Decimal("4000.00")
    assert result["annual_dividends"]["RUB"]["yoc"] == Decimal("0.16")
    # Four estimated dividend events in the horizon.
    events = [e for g in result["months"] for e in g["events"]]
    assert len(events) == 4
    assert all(e["kind"] == "dividend" and e["estimate"] is True for e in events)
    assert result["currency_totals"]["RUB"] == Decimal("4000.00")


@pytest.mark.django_db
def test_forecast_no_estimate_without_history(user):
    asset = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"), executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    result = income_forecast(pf, as_of=date(2024, 7, 1))
    assert result["has_estimates"] is False
    assert result["annual_dividends"] == {}
