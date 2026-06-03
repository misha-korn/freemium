from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache

from apps.marketdata.providers.base import Quote
from apps.marketdata.services import get_cached_quote


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
