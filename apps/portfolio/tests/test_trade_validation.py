"""Trade validation: can't sell more than held / sell without a position (Tier 1)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.portfolio.models import Asset, Portfolio, Transaction
from apps.portfolio.services import held_quantity


def _setup(user, *, bought="10"):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    if bought is not None:
        Transaction.objects.create(
            portfolio=pf, asset=asset, kind="BUY", quantity=Decimal(bought),
            price=Decimal("100"), fee=Decimal("0"),
            executed_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    return pf, asset


def _sell_payload(asset, qty):
    return {
        "asset": asset.pk, "kind": "SELL", "quantity": str(qty),
        "price": "150", "fee": "0", "executed_at": "2024-02-01T10:00", "note": "",
    }


# --- held_quantity service ------------------------------------------------- #
@pytest.mark.django_db
def test_held_quantity_nets_buys_and_sells(user):
    pf, asset = _setup(user, bought="10")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("4"),
        price=Decimal("120"), fee=Decimal("0"),
        executed_at=datetime(2024, 3, 1, tzinfo=UTC),
    )
    assert held_quantity(pf, asset) == Decimal("6")


@pytest.mark.django_db
def test_held_quantity_excludes_one_transaction(user):
    pf, asset = _setup(user, bought="10")
    sell = Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("4"),
        price=Decimal("120"), fee=Decimal("0"),
        executed_at=datetime(2024, 3, 1, tzinfo=UTC),
    )
    # Excluding the SELL leaves the full 10 bought.
    assert held_quantity(pf, asset, exclude_id=sell.pk) == Decimal("10")


# --- create view validation ------------------------------------------------ #
@pytest.mark.django_db
def test_cannot_sell_more_than_held(auth_client, user):
    pf, asset = _setup(user, bought="10")
    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": pf.pk}),
        _sell_payload(asset, "15"),
    )
    assert resp.status_code == 200  # re-rendered with error
    assert Transaction.objects.filter(kind="SELL").count() == 0
    assert b"you only hold" in resp.content


@pytest.mark.django_db
def test_can_sell_exactly_held(auth_client, user):
    pf, asset = _setup(user, bought="10")
    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": pf.pk}),
        _sell_payload(asset, "10"),
    )
    assert resp.status_code == 302
    assert Transaction.objects.filter(portfolio=pf, kind="SELL").count() == 1


@pytest.mark.django_db
def test_cannot_sell_without_a_position(auth_client, user):
    pf, asset = _setup(user, bought=None)  # never bought
    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": pf.pk}),
        _sell_payload(asset, "1"),
    )
    assert resp.status_code == 200
    assert Transaction.objects.count() == 0
    assert b"don&#x27;t hold any" in resp.content or b"don't hold any" in resp.content


@pytest.mark.django_db
def test_buy_is_never_restricted(auth_client, user):
    pf, asset = _setup(user, bought=None)
    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": pf.pk}),
        {
            "asset": asset.pk, "kind": "BUY", "quantity": "999",
            "price": "100", "fee": "0", "executed_at": "2024-01-01T10:00", "note": "",
        },
    )
    assert resp.status_code == 302
    assert Transaction.objects.filter(kind="BUY").count() == 1


# --- update view validation ------------------------------------------------ #
@pytest.mark.django_db
def test_editing_a_valid_sell_excludes_itself(auth_client, user):
    """Editing a legitimate SELL must not count that same SELL against the held qty."""
    pf, asset = _setup(user, bought="10")
    sell = Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("8"),
        price=Decimal("150"), fee=Decimal("0"),
        executed_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    # Edit the same SELL to 9 (still <= 10 held when excluding itself).
    resp = auth_client.post(
        reverse("portfolio:transaction_update", kwargs={"pk": sell.pk}),
        _sell_payload(asset, "9"),
    )
    assert resp.status_code == 302
    sell.refresh_from_db()
    assert sell.quantity == Decimal("9")


@pytest.mark.django_db
def test_editing_a_sell_beyond_held_is_blocked(auth_client, user):
    pf, asset = _setup(user, bought="10")
    sell = Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("5"),
        price=Decimal("150"), fee=Decimal("0"),
        executed_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    resp = auth_client.post(
        reverse("portfolio:transaction_update", kwargs={"pk": sell.pk}),
        _sell_payload(asset, "11"),  # only 10 held
    )
    assert resp.status_code == 200
    sell.refresh_from_db()
    assert sell.quantity == Decimal("5")  # unchanged
