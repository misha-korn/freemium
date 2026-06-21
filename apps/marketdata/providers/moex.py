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

# Primary order book for the most liquid MOEX shares; preferred when present.
PRIMARY_BOARD = "TQBR"

# Live market-data price columns, most "live" first. Falling back across these
# means we still return a price when the market is closed (weekends / after
# hours) and LAST is null but an intraday or session-close value exists.
MARKETDATA_PRICE_COLUMNS = ("LAST", "MARKETPRICE", "LCLOSEPRICE", "WAPRICE")
# Previous-session close, present even on days the security never traded.
SECURITIES_PRICE_COLUMNS = ("PREVPRICE", "PREVLEGALCLOSEPRICE", "PREVADMITTEDQUOTE")


class MoexQuoteProvider(QuoteProvider):
    """Fetch the latest available price from the public MOEX ISS REST API."""

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

        price = self._extract_price(payload)
        if price is None:
            return None
        return Quote(
            symbol=symbol.upper(),
            price=price,
            currency="RUB",
            as_of=datetime.now(UTC),
            source=self.name,
        )

    @classmethod
    def _extract_price(cls, payload: dict) -> Decimal | None:
        """Return the most recent available price.

        Tries the live market-data columns first (LAST, then intraday / close
        fallbacks); if today's session never traded, falls back to the
        previous-session close from the securities block. This keeps a quote
        available outside trading hours instead of showing nothing.
        """
        price = cls._price_from_block(payload, "marketdata", MARKETDATA_PRICE_COLUMNS)
        if price is None:
            price = cls._price_from_block(
                payload, "securities", SECURITIES_PRICE_COLUMNS
            )
        return price

    @staticmethod
    def _price_from_block(
        payload: dict, block_name: str, candidate_columns: tuple[str, ...]
    ) -> Decimal | None:
        """First positive price among candidate columns, preferring TQBR rows."""
        try:
            block = payload[block_name]
            columns = block["columns"]
            rows = block["data"]
        except (KeyError, TypeError) as exc:
            logger.warning("MOEX response shape unexpected (%s): %s", block_name, exc)
            return None

        present = [(col, columns.index(col)) for col in candidate_columns if col in columns]
        if not present:
            return None
        board_index = columns.index("BOARDID") if "BOARDID" in columns else None

        def board_rank(row: list) -> int:
            if board_index is None:
                return 1
            return 0 if row[board_index] == PRIMARY_BOARD else 1

        for row in sorted(rows, key=board_rank):
            for _col, index in present:
                price = _to_positive_decimal(row[index])
                if price is not None:
                    return price
        return None


def _to_positive_decimal(value: object) -> Decimal | None:
    """Coerce a MOEX cell to a positive Decimal, else None.

    MOEX uses null / empty / 0 to mean "no data"; a real share price is > 0.
    """
    if value in (None, ""):
        return None
    try:
        price = Decimal(str(value))
    except InvalidOperation:
        return None
    return price if price > 0 else None
