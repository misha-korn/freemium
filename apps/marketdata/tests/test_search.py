"""Ticker-search JSON endpoint used by the asset-form autocomplete."""
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.marketdata.providers.base import SymbolMatch


@pytest.mark.django_db
def test_symbol_search_returns_json(auth_client):
    matches = [SymbolMatch(ticker="SBER", name="Сбербанк")]
    with patch(
        "apps.marketdata.views.search_symbols", return_value=matches
    ) as search:
        resp = auth_client.get(
            reverse("marketdata:symbol_search"),
            {"q": "сбер", "market": "MOEX", "type": "STOCK"},
        )

    assert resp.status_code == 200
    assert resp.json()["results"] == [{"ticker": "SBER", "name": "Сбербанк"}]
    search.assert_called_once_with("MOEX", "сбер", "STOCK")


@pytest.mark.django_db
def test_symbol_search_empty_query_skips_lookup(auth_client):
    with patch("apps.marketdata.views.search_symbols") as search:
        resp = auth_client.get(reverse("marketdata:symbol_search"), {"q": ""})

    assert resp.json()["results"] == []
    search.assert_not_called()


@pytest.mark.django_db
def test_symbol_search_requires_login(client):
    resp = client.get(reverse("marketdata:symbol_search"), {"q": "x"})
    assert resp.status_code == 302
