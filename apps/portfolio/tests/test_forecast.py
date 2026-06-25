"""Forward income forecast from bond coupons — Tier 3 (#9)."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.portfolio import bonds
from apps.portfolio.forecast import income_forecast
from apps.portfolio.models import Asset, BondDetail, Portfolio, Transaction


def _bond_holding(user, *, qty="10", rate="8", freq=2, maturity=date(2030, 1, 1),
                  face="1000", currency="RUB"):
    asset = Asset.objects.create(
        ticker="OFZ", asset_type="BOND", market="MOEX", currency=currency
    )
    BondDetail.objects.create(
        asset=asset, face_value=Decimal(face), coupon_rate=Decimal(rate),
        coupon_frequency=freq, maturity_date=maturity,
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency=currency)
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal(qty),
        price=Decimal("980"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    return pf, asset


# --- upcoming_coupons (schedule) ------------------------------------------- #
@pytest.mark.django_db
def test_upcoming_coupons_lists_dates_in_window(user):
    _pf, asset = _bond_holding(user, maturity=date(2030, 1, 1), freq=2)  # Jan/Jul
    detail = asset.bond
    coupons = bonds.upcoming_coupons(detail, date(2024, 3, 1), date(2025, 3, 1))
    dates = [c["date"] for c in coupons]
    assert dates == [date(2024, 7, 1), date(2025, 1, 1)]
    assert all(c["amount"] == Decimal("40.00") for c in coupons)  # 1000*8%/2


@pytest.mark.django_db
def test_no_coupons_after_maturity(user):
    _pf, asset = _bond_holding(user, maturity=date(2024, 6, 1))
    coupons = bonds.upcoming_coupons(asset.bond, date(2024, 7, 1), date(2025, 7, 1))
    assert coupons == []


# --- income_forecast ------------------------------------------------------- #
@pytest.mark.django_db
def test_forecast_scales_by_quantity_and_groups_by_month(user):
    pf, _asset = _bond_holding(user, qty="10", maturity=date(2030, 1, 1), freq=2)
    result = income_forecast(pf, months=12, as_of=date(2024, 3, 1))

    # Two coupons in the next 12 months (Jul 2024, Jan 2025), 40 * 10 = 400 each.
    assert result["has_events"] is True
    assert result["currency_totals"]["RUB"] == Decimal("800.00")
    assert [(g["year"], g["month"]) for g in result["months"]] == [(2024, 7), (2025, 1)]
    assert result["months"][0]["events"][0]["amount"] == Decimal("400.00")
    assert result["months"][0]["totals"]["RUB"] == Decimal("400.00")


@pytest.mark.django_db
def test_forecast_empty_without_bond_details(user):
    asset = Asset.objects.create(
        ticker="RU000", asset_type="BOND", market="MOEX", currency="RUB"
    )  # no BondDetail
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("5"),
        price=Decimal("1000"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    result = income_forecast(pf, as_of=date(2024, 3, 1))
    assert result["has_events"] is False
    assert result["months"] == []


@pytest.mark.django_db
def test_forecast_excludes_stocks(user):
    stock = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    Transaction.objects.create(
        portfolio=pf, asset=stock, kind="BUY", quantity=Decimal("10"),
        price=Decimal("250"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    result = income_forecast(pf, as_of=date(2024, 3, 1))
    assert result["currency_totals"] == {}


# --- view ------------------------------------------------------------------ #
@pytest.mark.django_db
def test_forecast_page_renders(auth_client, user):
    pf, _asset = _bond_holding(user, maturity=date(2030, 1, 1))
    resp = auth_client.get(reverse("portfolio:income_forecast", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert resp.context["forecast"]["has_events"] is True


@pytest.mark.django_db
def test_forecast_page_requires_ownership(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="RUB")
    resp = auth_client.get(reverse("portfolio:income_forecast", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404
