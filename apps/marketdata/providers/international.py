"""International providers (Finnhub: price, name, search) + a Null fallback."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

from .base import Quote, QuoteProvider, SymbolMatch, prefix_matches

logger = logging.getLogger(__name__)

FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
FINNHUB_PROFILE_URL = "https://finnhub.io/api/v1/stock/profile2"
FINNHUB_SEARCH_URL = "https://finnhub.io/api/v1/search"
REQUEST_TIMEOUT = 10
SEARCH_LIMIT = 10


class FinnhubQuoteProvider(QuoteProvider):
    """Price / name / search from Finnhub. Requires FINNHUB_API_KEY."""

    name = "FINNHUB"

    def __init__(self, api_key: str | None = None, currency: str = "USD") -> None:
        self.api_key = (
            api_key if api_key is not None else getattr(settings, "FINNHUB_API_KEY", "")
        )
        self.currency = currency

    def _get_json(self, url: str, params: dict) -> dict | None:
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not configured")
            return None
        try:
            response = requests.get(
                url,
                params={**params, "token": self.api_key},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Finnhub request failed (%s): %s", url, exc)
            return None

    def get_quote(self, symbol: str) -> Quote | None:
        payload = self._get_json(FINNHUB_QUOTE_URL, {"symbol": symbol.upper()})
        if payload is None:
            return None
        raw_price = payload.get("c")  # "c" = current price
        if not raw_price:
            return None
        try:
            price = Decimal(str(raw_price))
        except InvalidOperation:
            return None
        return Quote(
            symbol=symbol.upper(),
            price=price,
            currency=self.currency,
            as_of=datetime.now(UTC),
            source=self.name,
        )

    def get_name(self, symbol: str) -> str | None:
        payload = self._get_json(FINNHUB_PROFILE_URL, {"symbol": symbol.upper()})
        if not payload:
            return None
        name = payload.get("name")
        return str(name).strip() if name else None

    def search(self, query: str, asset_type: str | None = None) -> list[SymbolMatch]:
        # asset_type is accepted for interface parity; Finnhub's free search has
        # no reliable type filter, so results are narrowed only by ticker/name prefix.
        payload = self._get_json(FINNHUB_SEARCH_URL, {"q": query})
        if not payload:
            return []
        matches: list[SymbolMatch] = []
        for item in payload.get("result", []):
            symbol = item.get("symbol")
            if not symbol:
                continue
            description = item.get("description") or ""
            match = SymbolMatch(ticker=str(symbol), name=str(description))
            if not prefix_matches(query, match):
                continue
            matches.append(match)
            if len(matches) >= SEARCH_LIMIT:
                break
        return matches


class NullQuoteProvider(QuoteProvider):
    """Safe default for unmapped markets — no quote, no name, no search."""

    name = "NULL"

    def get_quote(self, symbol: str) -> Quote | None:
        logger.debug("NullQuoteProvider: no quote for %s", symbol)
        return None
