"""Auto-import dividend history — Tier 3 (#9, facts half).

Pulls real per-share dividends (Twelve Data / MOEX, via ``marketdata.dividends``)
for the stocks/ETFs a portfolio has traded, and records a ``DividendPayment`` for
each past dividend using the **shares actually held before the ex-date** — so the
amount is a real figure (per-share × shares held then), not a guess.

These are facts; the forward *estimate* is a separate step. Quantities here are
the as-recorded (non-split-adjusted) counts that match the provider's historical
per-share amounts. Money is Decimal — never float.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.marketdata.dividends import sync_dividends

from .models import Asset, DividendPayment

if TYPE_CHECKING:
    from datetime import date

    from .models import Portfolio

_DIVIDEND_ASSET_TYPES = ("STOCK", "ETF", "FUND")
_MONEY = Decimal("0.01")


def quantity_as_of(portfolio: Portfolio, asset: Asset, before_date: date) -> Decimal:
    """Net shares of ``asset`` held strictly **before** ``before_date``.

    You must hold a share before its ex-date to receive the dividend, so trades on
    or after the ex-date don't count. As-recorded counts (not split-adjusted) so
    they match the provider's historical per-share amounts. Never negative.
    """
    held = Decimal("0")
    txns = portfolio.transactions.filter(
        asset=asset, executed_at__date__lt=before_date
    )
    for txn in txns:
        held += txn.quantity if txn.kind == "BUY" else -txn.quantity
    return held if held > 0 else Decimal("0")


def import_dividends(portfolio: Portfolio) -> dict:
    """Create ``DividendPayment`` rows from market dividend history.

    Returns ``{"created": int, "assets": int}``. Idempotent: a payment already
    recorded for an (asset, ex-date) is left alone, so re-running adds only new
    ones. Covers assets the portfolio has *ever* traded (so a dividend received
    while held but since sold is still captured).
    """
    today = timezone.now().date()
    asset_ids = list(
        portfolio.transactions.filter(asset__asset_type__in=_DIVIDEND_ASSET_TYPES)
        .values_list("asset_id", flat=True)
        .distinct()
    )
    assets = Asset.objects.filter(id__in=asset_ids)

    created = 0
    for asset in assets:
        sync_dividends(asset)  # populate AssetDividend (best-effort, cached)
        for record in asset.dividend_records.filter(ex_date__lte=today):
            quantity = quantity_as_of(portfolio, asset, record.ex_date)
            if quantity <= 0:
                continue
            if DividendPayment.objects.filter(
                portfolio=portfolio,
                asset=asset,
                paid_on=record.ex_date,
                kind=DividendPayment.Kind.DIVIDEND,
            ).exists():
                continue
            amount = (record.amount * quantity).quantize(_MONEY)
            if amount <= 0:
                continue
            DividendPayment.objects.create(
                portfolio=portfolio,
                asset=asset,
                kind=DividendPayment.Kind.DIVIDEND,
                amount=amount,
                tax_withheld=Decimal("0"),
                currency=record.currency or asset.currency,
                paid_on=record.ex_date,
                note="auto-import",
            )
            created += 1
    return {"created": created, "assets": len(asset_ids)}
