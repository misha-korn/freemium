"""Portfolio computation services — Stage 1.

All functions are pure (no DB writes). Money rule: Decimal only, never float.

Stage 2 TODO: current market value, unrealised P&L, and returns require live
price quotes. Do NOT fabricate prices here — portfolio_summary intentionally
omits market-value fields until Stage 2 wires up marketdata.Quote.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.portfolio.models import Asset, Portfolio


@dataclass(frozen=True)
class Position:
    """Computed holding for a single asset within a portfolio.

    All amounts are Decimal — never float.
    """

    asset: Asset
    quantity: Decimal
    avg_cost: Decimal  # per-unit average cost in asset currency
    invested: Decimal  # total cost basis (avg_cost × quantity)
    currency: str  # ISO 4217 code matching asset.currency


def compute_positions(portfolio: Portfolio) -> list[Position]:
    """Replay all transactions and return current open positions.

    Uses the average-cost method:
    - BUY: increases quantity; adds (price × quantity + fee) to cost basis.
    - SELL: reduces quantity; reduces invested by avg_cost × sold_qty.
      Realised P&L is not tracked in Stage 1.

    Transactions are processed in chronological order (executed_at, then id)
    so that same-second trades have a deterministic sequence.

    If a SELL would exceed the held quantity, quantity is clamped to 0 and
    excess units are silently ignored (data-quality guard).

    Returns only positions with quantity > 0, sorted by invested descending.
    """
    # Fetch once; select_related avoids per-row SQL for asset attributes.
    txns = (
        portfolio.transactions.select_related("asset")
        .order_by("executed_at", "id")
    )

    # Track per-asset state: {asset_id: [quantity, cost_basis]}
    # Using lists (mutable) for performance inside the loop.
    state: dict[int, list[Decimal]] = {}
    asset_map: dict[int, Asset] = {}

    for txn in txns:
        aid = txn.asset_id
        if aid not in state:
            state[aid] = [Decimal("0"), Decimal("0")]
            asset_map[aid] = txn.asset

        qty, basis = state[aid]

        if txn.kind == "BUY":
            # Money rule: Decimal only — never float.
            trade_cost = txn.price * txn.quantity + txn.fee
            state[aid] = [qty + txn.quantity, basis + trade_cost]

        elif txn.kind == "SELL":
            if qty <= Decimal("0"):
                # Nothing held — skip (data quality guard).
                continue

            sold = min(txn.quantity, qty)

            if qty > Decimal("0"):
                avg = basis / qty
            else:
                avg = Decimal("0")

            state[aid] = [
                qty - sold,
                basis - avg * sold,
            ]

    positions: list[Position] = []
    for aid, (qty, basis) in state.items():
        if qty <= Decimal("0"):
            continue
        asset = asset_map[aid]
        avg_cost = (basis / qty).quantize(Decimal("0.00000001")) if qty else Decimal("0")
        positions.append(
            Position(
                asset=asset,
                quantity=qty,
                avg_cost=avg_cost,
                invested=basis,
                currency=asset.currency,
            )
        )

    positions.sort(key=lambda p: p.invested, reverse=True)
    return positions


def portfolio_summary(portfolio: Portfolio) -> dict:
    """Return high-level aggregates for a portfolio.

    NOTE: current market value and percentage returns require live price
    quotes (Stage 2 — marketdata.Quote). They are intentionally absent here
    to avoid fabricated numbers being shown to users.

    Returns:
        {
            "positions_count": int,
            "invested_by_currency": dict[str, Decimal],  # cost basis per ISO code
            "base_currency": str,
        }
    """
    positions = compute_positions(portfolio)

    invested_by_currency: dict[str, Decimal] = {}
    for pos in positions:
        cur = pos.currency
        invested_by_currency[cur] = invested_by_currency.get(cur, Decimal("0")) + pos.invested

    return {
        "positions_count": len(positions),
        "invested_by_currency": invested_by_currency,
        "base_currency": portfolio.base_currency,
    }
