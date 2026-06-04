from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from apps.marketdata.models import PriceQuote
from apps.marketdata.providers.base import Quote
from apps.marketdata.services import (
    fetch_and_store_quote,
    get_cached_quote,
    latest_quote,
    latest_quotes,
    store_quote,
)
from apps.portfolio.models import Asset


def _sample_quote() -> Quote:
    return Quote(
        symbol="SBER",
        price=Decimal("100"),
        currency="RUB",
        as_of=datetime.now(UTC),
        source="MOEX",
    )


def test_get_cached_quote_fetches_then_serves_from_cache():
    cache.clear()
    quote = _sample_quote()
    provider = MagicMock()
    provider.get_quote.return_value = quote

    with patch("apps.marketdata.services.get_provider", return_value=provider):
        first = get_cached_quote("MOEX", "SBER")
        second = get_cached_quote("MOEX", "SBER")

    assert first == quote
    assert second == quote
    provider.get_quote.assert_called_once()  # second call hit the cache


def test_get_cached_quote_returns_none_when_unavailable():
    cache.clear()
    provider = MagicMock()
    provider.get_quote.return_value = None

    with patch("apps.marketdata.services.get_provider", return_value=provider):
        assert get_cached_quote("US", "NOPE") is None


@pytest.fixture
def asset(db) -> Asset:
    return Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )


@pytest.mark.django_db
def test_store_quote_is_idempotent(asset):
    quote = _sample_quote()
    first = store_quote(asset, quote)
    second = store_quote(asset, quote)  # same (asset, as_of, source)

    assert first.pk == second.pk
    assert PriceQuote.objects.filter(asset=asset).count() == 1
    assert first.price == Decimal("100")


@pytest.mark.django_db
def test_fetch_and_store_quote_persists_provider_result(asset):
    quote = _sample_quote()
    provider = MagicMock()
    provider.get_quote.return_value = quote

    with patch("apps.marketdata.services.get_provider", return_value=provider):
        stored = fetch_and_store_quote(asset)

    assert stored is not None
    assert stored.asset == asset
    assert PriceQuote.objects.count() == 1


@pytest.mark.django_db
def test_fetch_and_store_quote_returns_none_without_quote(asset):
    provider = MagicMock()
    provider.get_quote.return_value = None

    with patch("apps.marketdata.services.get_provider", return_value=provider):
        assert fetch_and_store_quote(asset) is None
    assert PriceQuote.objects.count() == 0


@pytest.mark.django_db
def test_latest_quote_returns_newest(asset):
    now = datetime.now(UTC)
    PriceQuote.objects.create(
        asset=asset, price=Decimal("90"), currency="RUB", as_of=now - timedelta(hours=1), source="MOEX"
    )
    newest = PriceQuote.objects.create(
        asset=asset, price=Decimal("110"), currency="RUB", as_of=now, source="MOEX"
    )
    assert latest_quote(asset) == newest


@pytest.mark.django_db
def test_latest_quotes_maps_each_asset_to_newest(asset):
    other = Asset.objects.create(
        ticker="GAZP", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    now = datetime.now(UTC)
    PriceQuote.objects.create(
        asset=asset, price=Decimal("90"), currency="RUB", as_of=now - timedelta(hours=2), source="MOEX"
    )
    newest_sber = PriceQuote.objects.create(
        asset=asset, price=Decimal("120"), currency="RUB", as_of=now, source="MOEX"
    )
    gazp_quote = PriceQuote.objects.create(
        asset=other, price=Decimal("150"), currency="RUB", as_of=now, source="MOEX"
    )

    result = latest_quotes([asset.id, other.id])
    assert result[asset.id] == newest_sber
    assert result[other.id] == gazp_quote


@pytest.mark.django_db
def test_latest_quotes_empty_input_returns_empty():
    assert latest_quotes([]) == {}
