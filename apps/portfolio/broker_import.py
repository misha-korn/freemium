"""Broker report import — Tier 2 (#4): a keyless, realistic auto-import.

Parses a broker report exported as **XLSX** (Tinkoff / Sber and similar) and
creates ``Transaction`` rows. Unlike the strict CSV import, broker layouts vary
and carry preamble/summary rows, so the parser is **tolerant**:

* it scans for the trades table by recognising the header row from keywords
  (Russian + English), not a fixed position;
* it maps columns by meaning (date / kind / ticker / quantity / price / …);
* it reads data rows until the table ends, reporting and skipping unreadable
  rows instead of aborting the whole file.

Assets are matched by ticker; an unknown instrument is **auto-created** with
best-effort fields (currency from the report, MOEX market when priced in RUB),
so the user need not pre-register every holding. No name lookup is done here to
keep the import offline and fast — the user can refresh prices/names later.

Money is Decimal — never float.
"""
from __future__ import annotations

import io
import logging
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import openpyxl
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import CURRENCY_CHOICES, Asset, Transaction

if TYPE_CHECKING:
    from .models import Portfolio

logger = logging.getLogger(__name__)

_VALID_CURRENCIES = {code for code, _label in CURRENCY_CHOICES}

# Column keywords, most specific first within each group so a trade-date column
# wins over a settlement-date column, etc. Matched as case-insensitive substrings.
_COLUMN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "date": ("дата заключ", "дата сделк", "дата операц", "trade date", "дата", "date"),
    "kind": (
        "вид сделки", "вид операции", "тип операции", "направление",
        "операция", "вид", "side", "operation", "buy/sell", "type",
    ),
    "ticker": (
        "код актива", "код инструмента", "тикер", "инструмент",
        "ticker", "symbol", "security", "актив",
    ),
    "quantity": ("количество", "кол-во", "quantity", "qty", "объем", "объём"),
    "price": ("цена за", "цена", "price"),
    "currency": ("валюта цены", "валюта", "currency"),
    "fee": ("комиссия брокера", "комиссия", "commission", "fee"),
    "isin": ("isin",),
}
_REQUIRED_COLUMNS = ("date", "kind", "ticker", "quantity", "price")

_BUY_WORDS = ("покупка", "купля", "приобрет", "покуп", "buy")
_SELL_WORDS = ("продажа", "продаж", "реализ", "sell")


class _SkipRow(Exception):
    """Raised for a blank/section row that should be silently skipped."""


def import_broker_xlsx(portfolio: Portfolio, raw: bytes) -> dict:
    """Create trades from a broker-report XLSX.

    Returns ``{"created": int, "created_assets": list[str], "errors": list[str]}``.
    """
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises various errors on a bad file
        logger.info("broker import: cannot open workbook: %s", exc)
        return {"created": 0, "created_assets": [], "errors": ["Couldn't read the file as an .xlsx workbook."]}

    created = 0
    created_assets: list[str] = []
    errors: list[str] = []
    table_found = False

    for worksheet in workbook.worksheets:
        table = _find_trades_table(worksheet)
        if table is None:
            continue
        table_found = True
        colmap, data_rows = table
        for row_no, cells in data_rows:
            try:
                txn, new_ticker = _build_from_row(portfolio, colmap, cells)
            except _SkipRow:
                continue
            except ValueError as exc:
                errors.append(f"row {row_no}: {exc}")
                continue
            txn.save()
            created += 1
            if new_ticker:
                created_assets.append(new_ticker)
        break  # first trades table is enough

    if not table_found:
        errors.append(
            "Couldn't find a trades table in the report — check it's a broker "
            "trades export (needs date, operation, ticker, quantity and price columns)."
        )
    return {"created": created, "created_assets": created_assets, "errors": errors}


# --------------------------------------------------------------------------- #
# Table detection
# --------------------------------------------------------------------------- #
def _find_trades_table(worksheet) -> tuple[dict[str, int], list[tuple[int, tuple]]] | None:
    """Locate the trades table: return (column map, [(row_no, cells)]) or None."""
    rows = list(worksheet.iter_rows(values_only=True))
    for index, cells in enumerate(rows):
        colmap = _match_header(cells)
        if colmap is None:
            continue
        data_rows: list[tuple[int, tuple]] = []
        started = False
        for offset, data in enumerate(rows[index + 1 :], start=index + 2):
            if _is_blank(data):
                if started:
                    break  # table ended
                continue  # skip blank rows between header and data
            data_rows.append((offset, data))
            started = True
        return colmap, data_rows
    return None


def _match_header(cells: tuple) -> dict[str, int] | None:
    """Map column groups to indices if ``cells`` looks like a trades header."""
    norm = [_norm(c) for c in cells]
    colmap: dict[str, int] = {}
    for group, keywords in _COLUMN_KEYWORDS.items():
        for keyword in keywords:
            idx = next((i for i, text in enumerate(norm) if keyword in text), None)
            if idx is not None:
                colmap[group] = idx
                break
    if all(key in colmap for key in _REQUIRED_COLUMNS):
        return colmap
    return None


# --------------------------------------------------------------------------- #
# Row -> Transaction
# --------------------------------------------------------------------------- #
def _build_from_row(
    portfolio: Portfolio, colmap: dict[str, int], cells: tuple
) -> tuple[Transaction, str | None]:
    ticker = _cell(cells, colmap.get("ticker"))
    ticker = str(ticker).strip() if ticker is not None else ""
    if not ticker:
        raise _SkipRow

    kind = _map_kind(_cell(cells, colmap.get("kind")))
    if kind is None:
        raise _SkipRow  # likely a total/section row, not a trade

    quantity = _to_decimal(_cell(cells, colmap.get("quantity")), "quantity")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    price = _to_decimal(_cell(cells, colmap.get("price")), "price")
    if price < 0:
        raise ValueError("price cannot be negative")

    fee_value = _cell(cells, colmap.get("fee"))
    fee = _to_decimal(fee_value, "fee") if fee_value not in (None, "") else Decimal("0")

    executed_at = _parse_when(_cell(cells, colmap.get("date")))
    if executed_at is None:
        raise ValueError("unreadable trade date")

    currency = str(_cell(cells, colmap.get("currency")) or "").strip().upper()
    isin = str(_cell(cells, colmap.get("isin")) or "").strip()
    asset, new_ticker = _resolve_or_create_asset(ticker, currency, isin)

    return (
        Transaction(
            portfolio=portfolio,
            asset=asset,
            kind=kind,
            quantity=quantity,
            price=price,
            fee=fee,
            executed_at=executed_at,
        ),
        new_ticker,
    )


def _resolve_or_create_asset(
    ticker: str, currency: str, isin: str
) -> tuple[Asset, str | None]:
    """Match an existing asset by ticker, else auto-create with inferred fields."""
    ticker = ticker.upper()
    existing = Asset.objects.filter(ticker__iexact=ticker).first()
    if existing is not None:
        return existing, None

    asset_currency = currency if currency in _VALID_CURRENCIES else "RUB"
    # RU brokers price domestic instruments in RUB on MOEX; everything else is
    # tagged GLOBAL as a safe catch-all the user can correct later.
    market = "MOEX" if asset_currency == "RUB" else "GLOBAL"
    asset = Asset.objects.create(
        ticker=ticker,
        asset_type="STOCK",
        market=market,
        currency=asset_currency,
        isin=isin,
    )
    return asset, ticker


# --------------------------------------------------------------------------- #
# Cell helpers
# --------------------------------------------------------------------------- #
def _cell(cells: tuple, index: int | None):
    if index is None or index >= len(cells):
        return None
    return cells[index]


def _norm(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("\xa0", " ")


def _is_blank(cells: tuple) -> bool:
    return all(c is None or str(c).strip() == "" for c in cells)


def _map_kind(value: object) -> str | None:
    text = _norm(value)
    if not text:
        return None
    if any(word in text for word in _BUY_WORDS) or text == "b":
        return "BUY"
    if any(word in text for word in _SELL_WORDS) or text == "s":
        return "SELL"
    return None


def _to_decimal(value: object, field: str) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"missing {field}")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    # Russian decimal comma vs thousands separators.
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"bad {field} value {value!r}") from None


def _parse_when(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        parsed = _parse_date_string(str(value).strip())
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _parse_date_string(text: str) -> datetime | None:
    parsed = parse_datetime(text)
    if parsed is not None:
        return parsed
    day = parse_date(text)
    if day is not None:
        return datetime.combine(day, time.min)
    # Russian d.m.Y (optionally with time): 01.02.2024 or 01.02.2024 14:30:00
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
