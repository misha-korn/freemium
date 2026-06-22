"""MOEX ISS provider (Russian market, no API key required): price, name, search."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import requests
from django.core.cache import cache

from .base import Quote, QuoteProvider, SymbolMatch, prefix_matches

logger = logging.getLogger(__name__)

MOEX_ISS_URL = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/securities/{symbol}.json"
)
MOEX_SEARCH_URL = "https://iss.moex.com/iss/securities.json"
REQUEST_TIMEOUT = 10
SEARCH_LIMIT = 10

# Primary order book for the most liquid MOEX shares; preferred when present.
PRIMARY_BOARD = "TQBR"

# Live market-data price columns, most "live" first. Falling back across these
# means we still return a price when the market is closed (weekends / after
# hours) and LAST is null but an intraday or session-close value exists.
MARKETDATA_PRICE_COLUMNS = ("LAST", "MARKETPRICE", "LCLOSEPRICE", "WAPRICE")
# Previous-session close, present even on days the security never traded.
SECURITIES_PRICE_COLUMNS = ("PREVPRICE", "PREVLEGALCLOSEPRICE", "PREVADMITTEDQUOTE")
# Display-name columns in the per-security endpoint's "securities" block.
SECURITIES_NAME_COLUMNS = ("SHORTNAME", "SECNAME", "NAME")
# Security groups the shares-market quote endpoint can actually price. Search is
# filtered to these so users pick tradable equities/funds — not bonds, indices
# or "fixing" reference instruments (e.g. FIXSBER) that have no share price.
PRICEABLE_GROUPS = {"stock_shares", "stock_etf", "stock_dr", "stock_ppif"}
# MOEX security groups per Asset.asset_type, so search narrows to the chosen
# instrument type. Types not listed (CRYPTO / OTHER) fall back to PRICEABLE_GROUPS.
GROUPS_BY_ASSET_TYPE = {
    "STOCK": {"stock_shares", "stock_dr"},
    "ETF": {"stock_etf", "stock_ppif"},
    "FUND": {"stock_ppif", "stock_etf"},
    "BOND": {"stock_bonds", "stock_eurobond"},
    "CURRENCY": {"currency_selt"},
}
# MOEX's text search (q=) needs ~3 chars. For shorter queries (and shares-market
# types) we filter a cached full list of shares-market instruments locally, so
# suggestions appear from the very first character.
MOEX_SHARES_LIST_URL = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/securities.json"
)
SHARES_INDEX_CACHE_KEY = "moex:shares_index"
SHARES_INDEX_TTL = 6 * 60 * 60  # seconds
SHORT_QUERY_LEN = 3
# Asset types covered by the shares-market list (everything priceable there).
INDEX_ASSET_TYPES = {"", "STOCK", "ETF", "FUND"}


class MoexQuoteProvider(QuoteProvider):
    """Price / name / search from the public MOEX ISS REST API."""

    name = "MOEX"

    def get_endpoint(self, symbol: str) -> str:
        return MOEX_ISS_URL.format(symbol=symbol.upper())

    @staticmethod
    def _get_json(url: str, params: dict) -> dict | None:
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("MOEX request failed (%s): %s", url, exc)
            return None

    def get_quote(self, symbol: str) -> Quote | None:
        payload = self._get_json(self.get_endpoint(symbol), {"iss.meta": "off"})
        if payload is None:
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

    def get_name(self, symbol: str) -> str | None:
        payload = self._get_json(self.get_endpoint(symbol), {"iss.meta": "off"})
        if payload is None:
            return None
        return self._first_name(payload)

    def search(self, query: str, asset_type: str | None = None) -> list[SymbolMatch]:
        query = query.strip()
        if not query:
            return []
        # Short shares-market queries: filter the cached full list locally so
        # suggestions work from 1 char (MOEX text search needs ~3).
        if (
            len(query) < SHORT_QUERY_LEN
            and (asset_type or "").upper() in INDEX_ASSET_TYPES
        ):
            hits = self._search_index(query)
            if hits:
                return hits
        payload = self._get_json(
            MOEX_SEARCH_URL,
            {"q": query, "iss.meta": "off", "limit": SEARCH_LIMIT},
        )
        if payload is None:
            return []
        return self._matches(payload, asset_type, query)

    # --- parsing helpers --------------------------------------------------- #
    @classmethod
    def _extract_price(cls, payload: dict) -> Decimal | None:
        """Most recent available price: live columns first, else previous close."""
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

        present = [(c, columns.index(c)) for c in candidate_columns if c in columns]
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

    @staticmethod
    def _first_name(payload: dict) -> str | None:
        """Pull SHORTNAME (preferring the TQBR row) from the securities block."""
        try:
            block = payload["securities"]
            columns = block["columns"]
            rows = block["data"]
        except (KeyError, TypeError):
            return None
        present = [columns.index(c) for c in SECURITIES_NAME_COLUMNS if c in columns]
        if not present:
            return None
        board_index = columns.index("BOARDID") if "BOARDID" in columns else None

        def board_rank(row: list) -> int:
            if board_index is None:
                return 1
            return 0 if row[board_index] == PRIMARY_BOARD else 1

        for row in sorted(rows, key=board_rank):
            for index in present:
                value = row[index] if index < len(row) else None
                if value:
                    return str(value).strip()
        return None

    @staticmethod
    def _matches(
        payload: dict, asset_type: str | None = None, query: str = ""
    ) -> list[SymbolMatch]:
        """Search hits from iss/securities.json (note: lowercase columns).

        Narrowed to the groups matching ``asset_type`` (else all priceable equity
        groups) and to ticker/name prefix matches of ``query``.
        """
        try:
            block = payload["securities"]
            columns = block["columns"]
            rows = block["data"]
        except (KeyError, TypeError):
            return []

        def col(field: str) -> int | None:
            return columns.index(field) if field in columns else None

        secid_i = col("secid")
        name_i = col("shortname") if col("shortname") is not None else col("name")
        traded_i = col("is_traded")
        group_i = col("group")
        if secid_i is None:
            return []

        allowed = GROUPS_BY_ASSET_TYPE.get((asset_type or "").upper(), PRICEABLE_GROUPS)
        matches: list[SymbolMatch] = []
        for row in rows:
            if traded_i is not None and not row[traded_i]:
                continue
            if group_i is not None and row[group_i] not in allowed:
                continue
            ticker = row[secid_i]
            if not ticker:
                continue
            name = row[name_i] if name_i is not None else ""
            match = SymbolMatch(ticker=str(ticker), name=str(name or ""))
            if not prefix_matches(query, match):
                continue
            matches.append(match)
            if len(matches) >= SEARCH_LIMIT:
                break
        return matches

    @classmethod
    def _shares_index(cls) -> list[SymbolMatch]:
        """Cached full list of shares-market instruments (SECID + SHORTNAME)."""
        cached = cache.get(SHARES_INDEX_CACHE_KEY)
        if cached is not None:
            return cached
        payload = cls._get_json(MOEX_SHARES_LIST_URL, {"iss.meta": "off"})
        index = cls._parse_index(payload) if payload else []
        cache.set(SHARES_INDEX_CACHE_KEY, index, SHARES_INDEX_TTL)
        return index

    @classmethod
    def _search_index(cls, query: str) -> list[SymbolMatch]:
        """Prefix match against the cached shares list (works from 1 char)."""
        hits = [m for m in cls._shares_index() if prefix_matches(query, m)]
        return hits[:SEARCH_LIMIT]

    @staticmethod
    def _parse_index(payload: dict) -> list[SymbolMatch]:
        """SECID + SHORTNAME from the shares-market list, deduped by ticker."""
        try:
            block = payload["securities"]
            columns = block["columns"]
            rows = block["data"]
        except (KeyError, TypeError):
            return []
        if "SECID" not in columns:
            return []
        secid_i = columns.index("SECID")
        name_i = columns.index("SHORTNAME") if "SHORTNAME" in columns else None
        seen: set[str] = set()
        index: list[SymbolMatch] = []
        for row in rows:
            secid = row[secid_i] if secid_i < len(row) else None
            if not secid or secid in seen:
                continue
            seen.add(secid)
            name = row[name_i] if name_i is not None and name_i < len(row) else ""
            index.append(SymbolMatch(ticker=str(secid), name=str(name or "")))
        return index


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
