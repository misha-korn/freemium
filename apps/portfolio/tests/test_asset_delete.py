"""Asset deletion: allowed when unused, blocked while trades reference it."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.portfolio.models import Asset, Portfolio, Transaction


@pytest.mark.django_db
def test_delete_unused_asset(auth_client):
    asset = Asset.objects.create(
        ticker="ZZZ", asset_type="STOCK", market="US", currency="USD"
    )
    resp = auth_client.post(reverse("portfolio:asset_delete", kwargs={"pk": asset.pk}))
    assert resp.status_code == 302
    assert not Asset.objects.filter(pk=asset.pk).exists()


@pytest.mark.django_db
def test_delete_blocked_when_asset_has_trades(auth_client, user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("1"),
        price=Decimal("100"), fee=Decimal("0"), executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    resp = auth_client.post(reverse("portfolio:asset_delete", kwargs={"pk": asset.pk}))
    assert resp.status_code == 302
    assert Asset.objects.filter(pk=asset.pk).exists()  # PROTECT keeps it


@pytest.mark.django_db
def test_asset_delete_requires_login(client):
    asset = Asset.objects.create(
        ticker="ZZZ", asset_type="STOCK", market="US", currency="USD"
    )
    resp = client.post(reverse("portfolio:asset_delete", kwargs={"pk": asset.pk}))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url
