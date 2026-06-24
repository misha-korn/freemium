"""Bond maths (НКД / coupons / maturity) + bond views — Tier 2 (#5)."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.portfolio import bonds
from apps.portfolio.models import Asset, BondDetail, Portfolio, Transaction


def _bond(ticker="OFZ26207", currency="RUB", *, face="1000", rate="8", freq=2,
          maturity=date(2025, 1, 1)) -> BondDetail:
    asset = Asset.objects.create(
        ticker=ticker, asset_type="BOND", market="MOEX", currency=currency
    )
    return BondDetail.objects.create(
        asset=asset, face_value=Decimal(face), coupon_rate=Decimal(rate),
        coupon_frequency=freq, maturity_date=maturity,
    )


# --- maths ----------------------------------------------------------------- #
@pytest.mark.django_db
def test_coupon_amount_per_period(user):
    detail = _bond(face="1000", rate="8", freq=2)
    # 1000 * 8% / 2 coupons = 40 per semi-annual coupon.
    assert detail.coupon_amount == Decimal("40")


@pytest.mark.django_db
def test_accrued_interest_linear_between_coupons(user):
    detail = _bond(face="1000", rate="8", freq=2, maturity=date(2025, 1, 1))
    # Coupon period 2024-07-01 .. 2025-01-01 (184 days); 92 days elapsed by Oct 1.
    accrued = bonds.accrued_interest(detail, date(2024, 10, 1))
    assert accrued == Decimal("20.00")  # 40 * 92/184


@pytest.mark.django_db
def test_accrued_zero_on_coupon_date(user):
    detail = _bond(maturity=date(2025, 1, 1), freq=2)
    # Exactly on a coupon boundary -> nothing accrued for the new period.
    assert bonds.accrued_interest(detail, date(2024, 7, 1)) == Decimal("0.00")


@pytest.mark.django_db
def test_next_coupon_and_days_to_maturity(user):
    detail = _bond(face="1000", rate="8", freq=2, maturity=date(2025, 1, 1))
    nxt = bonds.next_coupon(detail, date(2024, 10, 1))
    assert nxt["date"] == date(2025, 1, 1)
    assert nxt["amount"] == Decimal("40.00")
    assert bonds.days_to_maturity(detail, date(2024, 10, 1)) == 92


@pytest.mark.django_db
def test_matured_bond_has_no_accrual_or_next_coupon(user):
    detail = _bond(maturity=date(2024, 1, 1))
    assert bonds.accrued_interest(detail, date(2024, 6, 1)) == Decimal("0")
    assert bonds.next_coupon(detail, date(2024, 6, 1)) is None
    assert bonds.days_to_maturity(detail, date(2024, 6, 1)) < 0


@pytest.mark.django_db
def test_bond_summary_totals_scale_with_quantity(user):
    detail = _bond(face="1000", rate="8", freq=2, maturity=date(2025, 1, 1))
    summary = bonds.bond_summary(detail, date(2024, 10, 1), quantity=Decimal("10"))
    assert summary["accrued_interest"] == Decimal("20.00")
    assert summary["accrued_total"] == Decimal("200.00")  # 20 * 10
    assert summary["face_total"] == Decimal("10000.00")
    assert summary["matured"] is False
    assert summary["currency"] == "RUB"


# --- views ----------------------------------------------------------------- #
def _portfolio_holding_bond(user, detail: BondDetail) -> Portfolio:
    pf = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    Transaction.objects.create(
        portfolio=pf, asset=detail.asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("980"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    return pf


@pytest.mark.django_db
def test_bonds_page_lists_held_bond_with_summary(auth_client, user):
    detail = _bond(maturity=date(2030, 1, 1))
    pf = _portfolio_holding_bond(user, detail)

    resp = auth_client.get(reverse("portfolio:bonds", kwargs={"pk": pf.pk}))

    assert resp.status_code == 200
    rows = resp.context["bonds"]
    assert len(rows) == 1
    assert rows[0]["detail"] == detail
    assert rows[0]["summary"]["face_total"] == Decimal("10000.00")


@pytest.mark.django_db
def test_bonds_page_flags_missing_details(auth_client, user):
    asset = Asset.objects.create(
        ticker="RU000A", asset_type="BOND", market="MOEX", currency="RUB"
    )
    pf = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("5"),
        price=Decimal("1000"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 10, tzinfo=UTC),
    )

    resp = auth_client.get(reverse("portfolio:bonds", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert resp.context["bonds"][0]["detail"] is None
    assert b"set details" in resp.content


@pytest.mark.django_db
def test_non_bond_holdings_are_excluded(auth_client, user):
    stock = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    pf = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    Transaction.objects.create(
        portfolio=pf, asset=stock, kind="BUY", quantity=Decimal("1"),
        price=Decimal("250"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 10, tzinfo=UTC),
    )
    resp = auth_client.get(reverse("portfolio:bonds", kwargs={"pk": pf.pk}))
    assert resp.context["bonds"] == []


@pytest.mark.django_db
def test_owner_cannot_see_others_bonds(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="RUB")
    resp = auth_client.get(reverse("portfolio:bonds", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_create_and_edit_bond_details(auth_client, user):
    asset = Asset.objects.create(
        ticker="OFZ", asset_type="BOND", market="MOEX", currency="RUB"
    )
    pf = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    url = reverse("portfolio:bond_edit", kwargs={"pk": pf.pk, "asset_id": asset.pk})

    create = auth_client.post(url, {
        "face_value": "1000", "coupon_rate": "8.5",
        "coupon_frequency": "2", "maturity_date": "2030-01-01",
    })
    assert create.status_code == 302
    detail = BondDetail.objects.get(asset=asset)
    assert detail.coupon_rate == Decimal("8.5")

    edit = auth_client.post(url, {
        "face_value": "1000", "coupon_rate": "9",
        "coupon_frequency": "4", "maturity_date": "2030-01-01",
    })
    assert edit.status_code == 302
    detail.refresh_from_db()
    assert detail.coupon_frequency == 4
    assert BondDetail.objects.filter(asset=asset).count() == 1  # upsert, not duplicate


@pytest.mark.django_db
def test_bond_edit_rejects_non_bond_asset(auth_client, user):
    stock = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    url = reverse("portfolio:bond_edit", kwargs={"pk": pf.pk, "asset_id": stock.pk})
    assert auth_client.get(url).status_code == 404
