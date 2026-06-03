"""MOEX ISS quote provider (Russian market, no API key required)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import requests

from .base import Quote, QuoteProvider

logger = logging.getLogger(__name__)

MOEX_ISS_URL = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/securities/{symbol}.json"
)
REQUEST_TIMEOUT = 10


class MoexQuoteProvider(QuoteProvider):
    """Fetch last price from the public MOEX ISS REST API."""

    name = "MOEX"

    def get_endpoint(self, symbol: str) -> str:
        return MOEX_ISS_URL.format(symbol=symbol.upper())

    def get_quote(self, symbol: str) -> Quote | None:
        try:
            response = requests.get(
                self.get_endpoint(symbol),
                params={"iss.meta": "off"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("MOEX quote fetch failed for %s: %s", symbol, exc)
            return None

        price = self._extract_last_price(payload)
        if price is None:
            return None
        return Quote(
            symbol=symbol.upper(),
            price=price,
            currency="RUB",
            as_of=datetime.now(UTC),
            source=self.name,
        )

    @staticmethod
    def _extract_last_price(payload: dict) -> Decimal | None:
        """Pull the first non-null LAST value from the marketdata block."""
        try:
            block = payload["marketdata"]
            columns = block["columns"]
            rows = block["data"]
            last_index = columns.index("LAST")
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("MOEX response shape unexpected: %s", exc)
            return None

        for row in rows:
            value = row[last_index]
            if value is not None:
                try:
                    return Decimal(str(value))
                except InvalidOperation:
                    return None
        return None
