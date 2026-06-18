"""Price-alert evaluation + CRUD tests (Stage 5)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.marketdata.alerts import check_price_alerts
from apps.marketdata.models import PriceAlert, PriceQuote
from apps.marketdata.providers.base import Quote
from apps.marketdata.services import store_quote
from apps.notifications.models import Notification
from apps.portfolio.models import Asset


def _asset() -> Asset:
    return Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )


@pytest.mark.django_db
def test_above_alert_triggers_and_deactivates(user):
    asset = _asset()
    alert = PriceAlert.objects.create(
        user=user, asset=asset, threshold=Decimal("150"),
        direction=PriceAlert.Direction.ABOVE,
    )
    assert check_price_alerts(asset, Decimal("151")) == 1

    alert.refresh_from_db()
    assert alert.is_active is False
    assert alert.triggered_at is not None
    assert Notification.objects.filter(user=user, kind="PRICE_ALERT").count() == 1


@pytest.mark.django_db
def test_below_alert_triggers(user):
    asset = _asset()
    PriceAlert.objects.create(
        user=user, asset=asset, threshold=Decimal("90"),
        direction=PriceAlert.Direction.BELOW,
    )
    assert check_price_alerts(asset, Decimal("89")) == 1


@pytest.mark.django_db
def test_alert_not_triggered_when_not_crossed(user):
    asset = _asset()
    PriceAlert.objects.create(
        user=user, asset=asset, threshold=Decimal("150"),
        direction=PriceAlert.Direction.ABOVE,
    )
    assert check_price_alerts(asset, Decimal("149")) == 0
    assert Notification.objects.filter(kind="PRICE_ALERT").count() == 0


@pytest.mark.django_db
def test_inactive_alert_ignored(user):
    asset = _asset()
    PriceAlert.objects.create(
        user=user, asset=asset, threshold=Decimal("150"),
        direction=PriceAlert.Direction.ABOVE, is_active=False,
    )
    assert check_price_alerts(asset, Decimal("200")) == 0


@pytest.mark.django_db
def test_store_quote_triggers_alert(user):
    asset = _asset()
    PriceAlert.objects.create(
        user=user, asset=asset, threshold=Decimal("150"),
        direction=PriceAlert.Direction.ABOVE,
    )
    quote = Quote(
        symbol="AAPL", price=Decimal("160"), currency="USD",
        as_of=datetime.now(UTC), source="TEST",
    )
    store_quote(asset, quote)

    assert PriceQuote.objects.filter(asset=asset).count() == 1
    assert Notification.objects.filter(user=user, kind="PRICE_ALERT").count() == 1


@pytest.mark.django_db
def test_alert_crud_flow(auth_client, user):
    asset = _asset()
    # create
    resp = auth_client.post(
        reverse("marketdata:alert_create"),
        {"asset": asset.pk, "direction": "ABOVE", "threshold": "150"},
    )
    assert resp.status_code == 302
    alert = PriceAlert.objects.get(user=user, asset=asset)
    # list shows it
    resp = auth_client.get(reverse("marketdata:alert_list"))
    assert resp.status_code == 200
    assert b"AAPL" in resp.content
    # delete
    resp = auth_client.post(reverse("marketdata:alert_delete", kwargs={"pk": alert.pk}))
    assert resp.status_code == 302
    assert not PriceAlert.objects.filter(pk=alert.pk).exists()


@pytest.mark.django_db
def test_alert_list_requires_login(client):
    resp = client.get(reverse("marketdata:alert_list"))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url
