"""International quote providers (Finnhub) + a safe Null fallback."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

from .base import Quote, QuoteProvider

logger = logging.getLogger(__name__)

FINNHUB_URL = "https://finnhub.io/api/v1/quote"
REQUEST_TIMEOUT = 10


class FinnhubQuoteProvider(QuoteProvider):
    """Fetch current price from Finnhub. Requires FINNHUB_API_KEY."""

    name = "FINNHUB"

    def __init__(self, api_key: str | None = None, currency: str = "USD") -> None:
        self.api_key = (
            api_key if api_key is not None else getattr(settings, "FINNHUB_API_KEY", "")
        )
        self.currency = currency

    def get_quote(self, symbol: str) -> Quote | None:
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not configured; cannot fetch %s", symbol)
            return None
        try:
            response = requests.get(
                FINNHUB_URL,
                params={"symbol": symbol.upper(), "token": self.api_key},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Finnhub quote fetch failed for %s: %s", symbol, exc)
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


class NullQuoteProvider(QuoteProvider):
    """Safe default for unmapped markets — always returns None."""

    name = "NULL"

    def get_quote(self, symbol: str) -> Quote | None:
        logger.debug("NullQuoteProvider: no quote for %s", symbol)
        return None
