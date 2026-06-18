"""CSV trade import — Stage 5 (a keyless stand-in for broker auto-import).

Parses an uploaded CSV of trades and creates ``Transaction`` rows, matching each
line to an existing catalogue ``Asset`` by ticker (and market if given). Invalid
lines are collected and reported rather than aborting the whole file, so a user
can fix a few rows and re-import.

Expected columns: ticker, market, kind, quantity, price, fee, executed_at.
Money is Decimal — never float.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import Asset, Transaction

if TYPE_CHECKING:
    from .models import Portfolio


def import_trades_csv(portfolio: Portfolio, raw: bytes) -> dict:
    """Create trades from CSV bytes. Returns {"created": int, "errors": [str]}."""
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    pending: list[Transaction] = []
    errors: list[str] = []
    for line_no, row in enumerate(reader, start=2):  # line 1 is the header
        try:
            pending.append(_build_transaction(portfolio, row))
        except ValueError as exc:
            errors.append(f"line {line_no}: {exc}")

    for txn in pending:
        txn.save()
    return {"created": len(pending), "errors": errors}


def _build_transaction(portfolio: Portfolio, row: dict) -> Transaction:
    ticker = (row.get("ticker") or "").strip()
    if not ticker:
        raise ValueError("missing ticker")

    assets = Asset.objects.filter(ticker__iexact=ticker)
    market = (row.get("market") or "").strip()
    if market:
        assets = assets.filter(market__iexact=market)
    asset = assets.first()
    if asset is None:
        raise ValueError(f"unknown asset {ticker}")

    kind = (row.get("kind") or "").strip().upper()
    if kind not in ("BUY", "SELL"):
        raise ValueError(f"bad kind {kind!r} (expected BUY or SELL)")

    quantity = _decimal(row.get("quantity"), "quantity")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    price = _decimal(row.get("price"), "price")
    if price < 0:
        raise ValueError("price cannot be negative")
    fee = _decimal(row.get("fee") or "0", "fee")

    executed_at = _parse_when(row.get("executed_at") or "")
    if executed_at is None:
        raise ValueError("bad executed_at date")

    return Transaction(
        portfolio=portfolio,
        asset=asset,
        kind=kind,
        quantity=quantity,
        price=price,
        fee=fee,
        executed_at=executed_at,
    )


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"bad {field} value {value!r}") from None


def _parse_when(raw: str) -> datetime | None:
    raw = raw.strip()
    parsed = parse_datetime(raw)
    if parsed is None:
        day = parse_date(raw)
        if day is None:
            return None
        parsed = datetime.combine(day, time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed
