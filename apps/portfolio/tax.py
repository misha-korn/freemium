"""Realized-gains / tax reporting — Stage 5.

Replays a portfolio's trades and matches each SELL against earlier BUYs using
**FIFO** (first in, first out) to compute realized gain/loss per matched lot —
the basis of a yearly tax report. A single sell can span several buy lots, so it
may produce several ``RealizedLot`` rows.

Honesty/rules: money is Decimal; figures are in each asset's own currency and are
never mixed across currencies (``realized_summary`` groups by currency). Selling
more than is held is clamped (excess ignored), matching ``compute_positions``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from .corporate_actions import adjusted_quantity_price, splits_by_asset

if TYPE_CHECKING:
    from .models import Asset, Portfolio


@dataclass(frozen=True)
class RealizedLot:
    """One FIFO match: ``quantity`` of ``asset`` bought then sold.

    ``cost`` includes the allocated buy fee; ``proceeds`` is net of the allocated
    sell fee; ``gain`` is ``proceeds - cost`` (negative for a loss). All in the
    asset's own currency.
    """

    asset: Asset
    quantity: Decimal
    currency: str
    acquired_at: datetime
    disposed_at: datetime
    cost: Decimal
    proceeds: Decimal
    gain: Decimal

    @property
    def holding_days(self) -> int:
        return (self.disposed_at - self.acquired_at).days


def realized_gains(portfolio: Portfolio, *, year: int | None = None) -> list[RealizedLot]:
    """Return realized lots for ``portfolio``, optionally filtered by sell year."""
    txns = list(
        portfolio.transactions.select_related("asset").order_by("executed_at", "id")
    )
    # Split-adjust trades so share counts/prices are on today's terms (cost basis
    # preserved). No splits ⇒ a no-op (see corporate_actions).
    splits = splits_by_asset(txn.asset_id for txn in txns)

    # Per-asset FIFO queue of open buy lots: [remaining_qty, unit_cost, acquired_at].
    queues: dict[int, list[list]] = {}
    lots: list[RealizedLot] = []

    for txn in txns:
        queue = queues.setdefault(txn.asset_id, [])
        txn_qty, txn_price = adjusted_quantity_price(txn, splits.get(txn.asset_id))

        if txn.kind == "BUY":
            unit_cost = (txn_price * txn_qty + txn.fee) / txn_qty
            queue.append([txn_qty, unit_cost, txn.executed_at])
            continue

        if txn.kind != "SELL" or txn_qty <= 0:
            continue

        # Net per-unit proceeds: gross less this sell's fee, spread over the qty sold.
        unit_proceeds = (txn_price * txn_qty - txn.fee) / txn_qty
        remaining = txn_qty

        while remaining > 0 and queue:
            lot = queue[0]
            take = min(remaining, lot[0])
            cost = take * lot[1]
            proceeds = take * unit_proceeds
            lots.append(
                RealizedLot(
                    asset=txn.asset,
                    quantity=take,
                    currency=txn.asset.currency,
                    acquired_at=lot[2],
                    disposed_at=txn.executed_at,
                    cost=cost,
                    proceeds=proceeds,
                    gain=proceeds - cost,
                )
            )
            lot[0] -= take
            remaining -= take
            if lot[0] <= 0:
                queue.pop(0)
        # remaining > 0 here means selling more than held — excess ignored.

    if year is not None:
        lots = [lot for lot in lots if lot.disposed_at.year == year]
    return lots


def realized_summary(lots: list[RealizedLot]) -> dict[str, dict[str, Decimal]]:
    """Aggregate lots into per-currency totals: proceeds, cost, gain, count."""
    summary: dict[str, dict] = {}
    for lot in lots:
        bucket = summary.setdefault(
            lot.currency,
            {"proceeds": Decimal("0"), "cost": Decimal("0"), "gain": Decimal("0"), "count": 0},
        )
        bucket["proceeds"] += lot.proceeds
        bucket["cost"] += lot.cost
        bucket["gain"] += lot.gain
        bucket["count"] += 1
    return summary


def realized_years(portfolio: Portfolio) -> list[int]:
    """Distinct years in which this portfolio realized gains (newest first)."""
    return sorted({lot.disposed_at.year for lot in realized_gains(portfolio)}, reverse=True)
