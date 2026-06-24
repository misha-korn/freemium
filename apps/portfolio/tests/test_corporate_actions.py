"""Corporate actions — stock splits applied to positions, tax, validation (Tier 2 #7)."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.portfolio.models import Asset, CorporateAction, Portfolio, Transaction
from apps.portfolio.services import compute_positions, held_quantity
from apps.portfolio.tax import realized_gains


def _asset(ticker="AAPL", currency="USD", market="US"):
    return Asset.objects.create(
        ticker=ticker, asset_type="STOCK", market=market, currency=currency
    )


def _buy(pf, asset, qty, price, when):
    return Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal(qty),
        price=Decimal(price), fee=Decimal("0"), executed_at=when,
    )


def _split(asset, *, new, old, on):
    return CorporateAction.objects.create(
        asset=asset, kind="SPLIT", effective_date=on,
        new_shares=Decimal(new), old_shares=Decimal(old),
    )


# --- positions ------------------------------------------------------------- #
@pytest.mark.django_db
def test_split_adjusts_quantity_keeps_cost_basis(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", "100", datetime(2024, 1, 1, tzinfo=UTC))  # cost 1000
    _split(asset, new="2", old="1", on=date(2024, 6, 1))  # 2-for-1

    pos = compute_positions(pf)[0]
    assert pos.quantity == Decimal("20")          # 10 -> 20 shares
    assert pos.invested == Decimal("1000")        # cost basis unchanged
    assert pos.avg_cost == Decimal("50.00000000")  # 100 -> 50 per share


@pytest.mark.django_db
def test_no_split_leaves_positions_unchanged(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", "100", datetime(2024, 1, 1, tzinfo=UTC))
    pos = compute_positions(pf)[0]
    assert pos.quantity == Decimal("10")
    assert pos.invested == Decimal("1000")


@pytest.mark.django_db
def test_reverse_split_reduces_quantity(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "100", "5", datetime(2024, 1, 1, tzinfo=UTC))  # cost 500
    _split(asset, new="1", old="10", on=date(2024, 6, 1))  # 1-for-10 reverse

    pos = compute_positions(pf)[0]
    assert pos.quantity == Decimal("10")     # 100 -> 10
    assert pos.invested == Decimal("500")    # unchanged


@pytest.mark.django_db
def test_trade_after_split_is_not_adjusted(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _split(asset, new="2", old="1", on=date(2024, 6, 1))
    _buy(pf, asset, "10", "50", datetime(2024, 7, 1, tzinfo=UTC))  # already post-split

    pos = compute_positions(pf)[0]
    assert pos.quantity == Decimal("10")  # bought after the split -> no adjustment


# --- tax + validation ------------------------------------------------------ #
@pytest.mark.django_db
def test_realized_gain_correct_across_split(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", "100", datetime(2024, 1, 1, tzinfo=UTC))   # cost 1000
    _split(asset, new="2", old="1", on=date(2024, 6, 1))
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("20"),
        price=Decimal("60"), fee=Decimal("0"),
        executed_at=datetime(2024, 7, 1, tzinfo=UTC),
    )  # sell all 20 post-split shares @ 60 -> proceeds 1200

    lots = realized_gains(pf)
    assert sum(lot.gain for lot in lots) == Decimal("200")  # 1200 - 1000


@pytest.mark.django_db
def test_held_quantity_is_split_adjusted(user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", "100", datetime(2024, 1, 1, tzinfo=UTC))
    _split(asset, new="2", old="1", on=date(2024, 6, 1))
    assert held_quantity(pf, asset) == Decimal("20")


@pytest.mark.django_db
def test_can_sell_post_split_quantity_via_form(auth_client, user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", "100", datetime(2024, 1, 1, tzinfo=UTC))
    _split(asset, new="2", old="1", on=date(2024, 6, 1))  # now hold 20

    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": pf.pk}),
        {
            "asset": asset.pk, "kind": "SELL", "quantity": "18",
            "price": "60", "fee": "0", "executed_at": "2024-07-01T10:00", "note": "",
        },
    )
    assert resp.status_code == 302  # 18 <= 20 post-split -> allowed
    assert Transaction.objects.filter(portfolio=pf, kind="SELL").count() == 1


# --- views ----------------------------------------------------------------- #
@pytest.mark.django_db
def test_add_and_delete_split(auth_client, user):
    asset = _asset()
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, asset, "10", "100", datetime(2024, 1, 1, tzinfo=UTC))
    url = reverse("portfolio:corporate_actions", kwargs={"pk": pf.pk})

    add = auth_client.post(url, {
        "asset": asset.pk, "effective_date": "2024-06-01",
        "new_shares": "2", "old_shares": "1", "note": "",
    })
    assert add.status_code == 302
    action = CorporateAction.objects.get(asset=asset)

    delete = auth_client.post(
        reverse("portfolio:corporate_action_delete", kwargs={"pk": pf.pk, "action_id": action.pk})
    )
    assert delete.status_code == 302
    assert not CorporateAction.objects.filter(pk=action.pk).exists()


@pytest.mark.django_db
def test_split_form_rejects_untraded_asset(auth_client, user):
    traded = _asset("AAPL")
    other = _asset("TSLA")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    _buy(pf, traded, "1", "100", datetime(2024, 1, 1, tzinfo=UTC))
    url = reverse("portfolio:corporate_actions", kwargs={"pk": pf.pk})

    resp = auth_client.post(url, {
        "asset": other.pk, "effective_date": "2024-06-01",
        "new_shares": "2", "old_shares": "1", "note": "",
    })
    assert resp.status_code == 200  # re-rendered: TSLA isn't traded in this portfolio
    assert CorporateAction.objects.count() == 0


@pytest.mark.django_db
def test_corporate_actions_requires_ownership(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:corporate_actions", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404
