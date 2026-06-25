"""Dividend data layer: Twelve Data + MOEX parsing, currency, sync (Tier 3 #9)."""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.marketdata import dividends
from apps.marketdata.models import AssetDividend
from apps.portfolio.models import Asset


def _response(payload):
    resp = Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@override_settings(TWELVE_DATA_API_KEY="testkey")
@pytest.mark.django_db
def test_twelvedata_dividends_parsed():
    asset = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    payload = {
        "meta": {"currency": "USD"},
        "dividends": [
            {"ex_date": "2024-05-10", "amount": 0.25},
            {"ex_date": "2024-02-09", "amount": 0.24},
        ],
    }
    with patch("apps.marketdata.dividends.requests.get", return_value=_response(payload)):
        records = dividends.fetch_dividends(asset)

    assert [r.ex_date for r in records] == [date(2024, 5, 10), date(2024, 2, 9)]
    assert records[0].amount == Decimal("0.25")
    assert records[0].currency == "USD"


@override_settings(TWELVE_DATA_API_KEY="")
@pytest.mark.django_db
def test_twelvedata_skipped_without_key():
    asset = Asset.objects.create(ticker="MSFT", asset_type="STOCK", market="US", currency="USD")
    with patch("apps.marketdata.dividends.requests.get") as get:
        records = dividends.fetch_dividends(asset)
    assert records == []
    get.assert_not_called()  # no network call without a key


@pytest.mark.django_db
def test_moex_dividends_parsed_and_currency_normalised():
    asset = Asset.objects.create(ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB")
    payload = {
        "dividends": {
            "columns": ["secid", "isin", "registryclosedate", "value", "currencyid"],
            "data": [
                ["SBER", "RU000", "2024-05-10", 33.3, "SUR"],  # legacy code -> RUB
                ["SBER", "RU000", "2023-05-11", 25.0, "RUB"],
            ],
        }
    }
    with patch("apps.marketdata.dividends.requests.get", return_value=_response(payload)):
        records = dividends.fetch_dividends(asset)

    assert len(records) == 2
    assert records[0].amount == Decimal("33.3")
    assert all(r.currency == "RUB" for r in records)


@override_settings(TWELVE_DATA_API_KEY="testkey")
@pytest.mark.django_db
def test_sync_dividends_persists_rows_idempotently():
    asset = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    payload = {"meta": {"currency": "USD"}, "dividends": [{"ex_date": "2024-05-10", "amount": 0.25}]}
    with patch("apps.marketdata.dividends.requests.get", return_value=_response(payload)):
        first = dividends.sync_dividends(asset)
        cache.clear()
        second = dividends.sync_dividends(asset)

    assert first == 1
    assert second == 0  # get_or_create -> no duplicate
    assert AssetDividend.objects.filter(asset=asset).count() == 1


@override_settings(TWELVE_DATA_API_KEY="testkey")
@pytest.mark.django_db
def test_network_failure_returns_empty():
    asset = Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    import requests

    with patch("apps.marketdata.dividends.requests.get", side_effect=requests.RequestException):
        assert dividends.fetch_dividends(asset) == []
