from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.marketdata.providers.international import (
    FinnhubQuoteProvider,
    NullQuoteProvider,
)
from apps.marketdata.providers.moex import MoexQuoteProvider
from apps.marketdata.providers.registry import get_provider


def test_registry_maps_markets_to_providers():
    assert get_provider("MOEX").name == "MOEX"
    assert get_provider("US").name == "FINNHUB"
    assert get_provider("GLOBAL").name == "FINNHUB"
    assert get_provider("???").name == "NULL"


def test_null_provider_returns_none():
    assert NullQuoteProvider().get_quote("ANYTHING") is None


def test_finnhub_without_key_returns_none():
    assert FinnhubQuoteProvider(api_key="").get_quote("AAPL") is None


def test_moex_parses_last_price_from_mocked_response():
    payload = {
        "marketdata": {
            "columns": ["SECID", "LAST"],
            "data": [["SBER", 250.5]],
        }
    }
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None

    with patch(
        "apps.marketdata.providers.moex.requests.get", return_value=mock_response
    ):
        quote = MoexQuoteProvider().get_quote("SBER")

    assert quote is not None
    assert quote.price == Decimal("250.5")
    assert quote.currency == "RUB"
    assert quote.source == "MOEX"
