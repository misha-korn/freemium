"""Asset creation auto-fills the company/security name from the provider."""
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.portfolio.models import Asset

BASE_DATA = {
    "ticker": "SBER",
    "name": "",
    "asset_type": "STOCK",
    "market": "MOEX",
    "currency": "RUB",
    "isin": "",
}


@pytest.mark.django_db
def test_blank_name_is_autofilled_from_provider(auth_client):
    with patch(
        "apps.portfolio.views.resolve_asset_name", return_value="Сбербанк"
    ) as resolver:
        auth_client.post(reverse("portfolio:asset_create"), BASE_DATA)

    resolver.assert_called_once_with("MOEX", "SBER")
    assert Asset.objects.get(ticker="SBER").name == "Сбербанк"


@pytest.mark.django_db
def test_provided_name_is_not_overwritten(auth_client):
    data = {**BASE_DATA, "name": "My Sber"}
    with patch("apps.portfolio.views.resolve_asset_name") as resolver:
        auth_client.post(reverse("portfolio:asset_create"), data)

    resolver.assert_not_called()
    assert Asset.objects.get(ticker="SBER").name == "My Sber"


@pytest.mark.django_db
def test_unresolved_name_leaves_asset_nameless(auth_client):
    with patch("apps.portfolio.views.resolve_asset_name", return_value=None):
        auth_client.post(reverse("portfolio:asset_create"), BASE_DATA)

    assert Asset.objects.get(ticker="SBER").name == ""
