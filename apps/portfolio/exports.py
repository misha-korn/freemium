"""Data export — Stage 5 (Pro).

Builds CSV and Excel exports of a portfolio's transactions and its realized-gains
tax report. CSV is written with a UTF-8 BOM so Excel opens Cyrillic correctly;
Excel uses openpyxl. Money is rounded to 2 dp for display only — the underlying
figures stay full-precision Decimal.
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import TYPE_CHECKING

from openpyxl import Workbook

from .tax import realized_gains, realized_summary

if TYPE_CHECKING:
    from .models import Portfolio

_MONEY = Decimal("0.01")


def _money(value: Decimal) -> str:
    return str(value.quantize(_MONEY))


# --------------------------------------------------------------------------- #
# Row builders (shared by CSV + Excel)
# --------------------------------------------------------------------------- #
_TXN_HEADERS = ["Date", "Type", "Asset", "Market", "Quantity", "Price", "Fee", "Currency"]
_TAX_HEADERS = [
    "Asset", "Currency", "Acquired", "Disposed", "Quantity",
    "Cost", "Proceeds", "Gain", "Holding days",
]


def _txn_rows(portfolio: Portfolio) -> list[list[str]]:
    rows = []
    for txn in portfolio.transactions.select_related("asset").order_by("executed_at", "id"):
        rows.append([
            txn.executed_at.date().isoformat(),
            txn.get_kind_display(),
            txn.asset.ticker,
            txn.asset.market,
            str(txn.quantity.normalize()),
            _money(txn.price),
            _money(txn.fee),
            txn.asset.currency,
        ])
    return rows


def _tax_rows(portfolio: Portfolio, year: int | None) -> list[list[str]]:
    rows = []
    for lot in realized_gains(portfolio, year=year):
        rows.append([
            lot.asset.ticker,
            lot.currency,
            lot.acquired_at.date().isoformat(),
            lot.disposed_at.date().isoformat(),
            str(lot.quantity.normalize()),
            _money(lot.cost),
            _money(lot.proceeds),
            _money(lot.gain),
            str(lot.holding_days),
        ])
    return rows


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def _csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    # UTF-8 BOM so Excel detects encoding (Cyrillic tickers/notes render correctly).
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def transactions_csv(portfolio: Portfolio) -> bytes:
    return _csv_bytes(_TXN_HEADERS, _txn_rows(portfolio))


def tax_csv(portfolio: Portfolio, year: int | None = None) -> bytes:
    return _csv_bytes(_TAX_HEADERS, _tax_rows(portfolio, year))


# --------------------------------------------------------------------------- #
# Excel (.xlsx)
# --------------------------------------------------------------------------- #
def tax_xlsx(portfolio: Portfolio, year: int | None = None) -> bytes:
    """Workbook with a Realized-gains sheet and a per-currency Summary sheet."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Realized gains"
    ws.append(_TAX_HEADERS)
    for row in _tax_rows(portfolio, year):
        ws.append(row)

    summary = wb.create_sheet("Summary")
    summary.append(["Currency", "Proceeds", "Cost", "Gain", "Lots"])
    for currency, totals in realized_summary(realized_gains(portfolio, year=year)).items():
        summary.append([
            currency,
            _money(totals["proceeds"]),
            _money(totals["cost"]),
            _money(totals["gain"]),
            totals["count"],
        ])

    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()
