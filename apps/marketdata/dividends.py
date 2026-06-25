"""Dividend data — fetch real per-share dividends from market providers.

Two sources, dispatched by the asset's market:
- **MOEX ISS** (RU, no key): ``/securities/{SECID}/dividends.json``.
- **Twelve Data** (international, ``TWELVE_DATA_API_KEY``): ``/dividends``.

Fetches are best-effort and cached: a network/parse failure yields an empty list
rather than raising, exactly like the quote providers. Money is Decimal — never
float. Records are stored as ``AssetDividend`` rows for reuse (history import,
forward estimate).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_date

from .models import AssetDividend

try:  # Asset is only needed for typing.
    from apps.portfolio.models import Asset
except Exception:  # pragma: no cover - avoids import cycles at startup
    Asset = object  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

TWELVE_DATA_URL = "https://api.twelvedata.com/dividends"
MOEX_DIVIDENDS_URL = "https://iss.moex.com/iss/securities/{symbol}/dividends.json"
REQUEST_TIMEOUT = 10
CACHE_TTL = 12 * 60 * 60  # dividends change rarely; cache 12h
# How far back to ask Twelve Data for history.
HISTORY_START = "2015-01-01"
# Map provider currency codes to our ISO codes (MOEX uses the legacy "SUR").
_CURRENCY_ALIASES = {"SUR": "RUB", "RUR": "RUB"}
_VALID_CURRENCIES = {"RUB", "USD", "EUR", "GBP", "CNY"}


@dataclass(frozen=True)
class DividendRecord:
    """One per-share dividend on an ex-date."""

    ex_date: date
    amount: Decimal
    currency: str


def fetch_dividends(asset: Asset) -> list[DividendRecord]:
    """Real per-share dividends for ``asset`` from its market provider (cached)."""
    market = (asset.market or "").upper()
    symbol = asset.ticker.upper()
    cache_key = f"dividends:{market}:{symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if market == "MOEX":
        records = _moex_dividends(symbol)
    else:
        records = _twelvedata_dividends(symbol)
    cache.set(cache_key, records, CACHE_TTL)
    return records


def sync_dividends(asset: Asset) -> int:
    """Fetch and persist dividends as ``AssetDividend`` rows; return how many new."""
    stored = 0
    for record in fetch_dividends(asset):
        _, created = AssetDividend.objects.get_or_create(
            asset=asset,
            ex_date=record.ex_date,
            source="MOEX" if (asset.market or "").upper() == "MOEX" else "TWELVE_DATA",
            defaults={"amount": record.amount, "currency": record.currency},
        )
        stored += int(created)
    return stored


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def _get_json(url: str, params: dict) -> dict | None:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Dividend request failed (%s): %s", url, exc)
        return None


def _twelvedata_dividends(symbol: str) -> list[DividendRecord]:
    key = getattr(settings, "TWELVE_DATA_API_KEY", "")
    if not key:
        logger.info("TWELVE_DATA_API_KEY not configured; skipping dividend fetch")
        return []
    payload = _get_json(
        TWELVE_DATA_URL,
        {
            "symbol": symbol,
            "apikey": key,
            "start_date": HISTORY_START,
            "end_date": date.today().isoformat(),
        },
    )
    if not payload or payload.get("status") == "error" or "dividends" not in payload:
        return []
    currency = _normalise_currency((payload.get("meta") or {}).get("currency"))
    records: list[DividendRecord] = []
    for row in payload["dividends"]:
        ex_date = parse_date(str(row.get("ex_date") or ""))
        amount = _to_decimal(row.get("amount"))
        if ex_date is None or amount is None or amount <= 0:
            continue
        records.append(DividendRecord(ex_date=ex_date, amount=amount, currency=currency))
    return records


def _moex_dividends(symbol: str) -> list[DividendRecord]:
    # Encode the ticker into the URL path (it can't break out to another host).
    url = MOEX_DIVIDENDS_URL.format(symbol=quote(symbol, safe=""))
    payload = _get_json(url, {"iss.meta": "off"})
    if not payload:
        return []
    try:
        block = payload["dividends"]
        columns = block["columns"]
        rows = block["data"]
    except (KeyError, TypeError):
        return []

    def col(name: str) -> int | None:
        return columns.index(name) if name in columns else None

    date_i = col("registryclosedate")
    value_i = col("value")
    currency_i = col("currencyid")
    if date_i is None or value_i is None:
        return []

    records: list[DividendRecord] = []
    for row in rows:
        ex_date = parse_date(str(row[date_i] or ""))
        amount = _to_decimal(row[value_i])
        if ex_date is None or amount is None or amount <= 0:
            continue
        currency = _normalise_currency(row[currency_i] if currency_i is not None else None)
        records.append(DividendRecord(ex_date=ex_date, amount=amount, currency=currency))
    return records


def _normalise_currency(value: object) -> str:
    code = str(value or "").strip().upper()
    code = _CURRENCY_ALIASES.get(code, code)
    return code if code in _VALID_CURRENCIES else "RUB"


def _to_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None
