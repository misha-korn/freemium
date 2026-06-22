from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.marketdata.providers.base import SymbolMatch
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


def _mock_get(payload):
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    return patch(
        "apps.marketdata.providers.moex.requests.get", return_value=mock_response
    )


def test_moex_falls_back_to_previous_close_when_market_closed():
    """Outside trading hours LAST is null; use the previous-session close."""
    payload = {
        "marketdata": {
            "columns": ["SECID", "BOARDID", "LAST", "MARKETPRICE"],
            "data": [["SBER", "TQBR", None, None]],
        },
        "securities": {
            "columns": ["SECID", "BOARDID", "PREVPRICE"],
            # SMAL listed first to prove TQBR (primary board) wins regardless.
            "data": [["SBER", "SMAL", 240.0], ["SBER", "TQBR", 245.7]],
        },
    }
    with _mock_get(payload):
        quote = MoexQuoteProvider().get_quote("SBER")

    assert quote is not None
    assert quote.price == Decimal("245.7")


def test_moex_returns_none_when_no_price_anywhere():
    payload = {
        "marketdata": {"columns": ["SECID", "LAST"], "data": [["SBER", None]]},
        "securities": {"columns": ["SECID", "PREVPRICE"], "data": [["SBER", 0]]},
    }
    with _mock_get(payload):
        assert MoexQuoteProvider().get_quote("SBER") is None


def test_moex_get_name_prefers_primary_board():
    payload = {
        "securities": {
            "columns": ["SECID", "BOARDID", "SHORTNAME"],
            "data": [["SBER", "SMAL", "Сбер-смолл"], ["SBER", "TQBR", "Сбербанк"]],
        }
    }
    with _mock_get(payload):
        assert MoexQuoteProvider().get_name("SBER") == "Сбербанк"


def test_moex_search_returns_traded_matches():
    payload = {
        "securities": {
            "columns": ["secid", "shortname", "is_traded"],
            "data": [
                ["SBER", "Сбербанк", 1],
                ["SBERP", "Сбербанк-п", 1],
                ["OLD", "Делистинг", 0],
            ],
        }
    }
    with _mock_get(payload):
        matches = MoexQuoteProvider().search("сбер")
    assert [m.ticker for m in matches] == ["SBER", "SBERP"]  # untraded row skipped
    assert matches[0].name == "Сбербанк"


def test_moex_search_filters_out_non_shares():
    """Drop bonds / indices / fixing instruments — only priceable equities."""
    payload = {
        "securities": {
            "columns": ["secid", "shortname", "is_traded", "group"],
            "data": [
                ["SBER", "Сбербанк", 1, "stock_shares"],
                ["SBMX", "Сбер ETF", 1, "stock_etf"],
                ["FIXSBER", "Фиксинг МосБиржи SBER", 1, "stock_index"],
                ["SU26240", "ОФЗ 26240", 1, "stock_bonds"],
            ],
        }
    }
    with _mock_get(payload):
        matches = MoexQuoteProvider().search("сбер")
    assert [m.ticker for m in matches] == ["SBER", "SBMX"]


def _mock_intl_get(payload):
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    return patch(
        "apps.marketdata.providers.international.requests.get",
        return_value=mock_response,
    )


def test_finnhub_get_name_from_profile():
    with _mock_intl_get({"name": "Apple Inc", "ticker": "AAPL"}):
        assert FinnhubQuoteProvider(api_key="k").get_name("AAPL") == "Apple Inc"


def test_finnhub_search_maps_results():
    payload = {
        "count": 2,
        "result": [
            {"symbol": "AAPL", "description": "APPLE INC"},
            {"symbol": "APLE", "description": "APPLE HOSPITALITY REIT"},
        ],
    }
    with _mock_intl_get(payload):
        matches = FinnhubQuoteProvider(api_key="k").search("apple")
    assert [m.ticker for m in matches] == ["AAPL", "APLE"]
    assert matches[0].name == "APPLE INC"


def test_null_provider_has_no_name_or_search():
    assert NullQuoteProvider().get_name("X") is None
    assert NullQuoteProvider().search("X") == []


def test_moex_search_narrows_to_asset_type():
    """asset_type selects the matching MOEX groups (BOND → bonds, STOCK → shares)."""
    payload = {
        "securities": {
            "columns": ["secid", "shortname", "is_traded", "group"],
            "data": [
                ["SBER", "Сбербанк", 1, "stock_shares"],
                ["SBMX", "Сбер ETF", 1, "stock_etf"],
                ["SBRB", "Сбербанк обл", 1, "stock_bonds"],
            ],
        }
    }
    with _mock_get(payload):
        bonds = MoexQuoteProvider().search("сбер", asset_type="BOND")
        stocks = MoexQuoteProvider().search("сбер", asset_type="STOCK")
    assert [m.ticker for m in bonds] == ["SBRB"]
    assert [m.ticker for m in stocks] == ["SBER"]


def test_moex_short_query_filters_cached_index():
    """A 1–2 char stock query filters the cached shares list (no 3-char floor)."""
    index = [
        SymbolMatch("SBER", "Сбербанк"),
        SymbolMatch("SBERP", "Сбербанк-п"),
        SymbolMatch("GAZP", "Газпром"),
    ]
    with patch.object(MoexQuoteProvider, "_shares_index", return_value=index):
        matches = MoexQuoteProvider().search("s", asset_type="STOCK")
    assert [m.ticker for m in matches] == ["SBER", "SBERP"]
