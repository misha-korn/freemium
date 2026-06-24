"""Corporate actions — Tier 2 (#7): stock splits applied to trade replay.

A split changes the share count and per-share price but not the value held, so a
position's **cost basis must stay intact**. We adjust each trade executed *before*
a split: quantity × factor, price ÷ factor (factor = new ÷ old). Cost
(quantity × price) is therefore unchanged, while the share count and average cost
end up in today's post-split terms — matching current market prices.

These helpers are shared by ``compute_positions``, the FIFO tax report and the
trade-validation ``held_quantity`` so all three agree on split-adjusted shares.
Money/quantity is Decimal — never float.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from .models import CorporateAction

if TYPE_CHECKING:
    from .models import Transaction


def splits_by_asset(asset_ids: Iterable[int]) -> dict[int, list[CorporateAction]]:
    """Map each asset id to its splits (only assets that have any)."""
    ids = list(dict.fromkeys(asset_ids))
    if not ids:
        return {}
    grouped: dict[int, list[CorporateAction]] = {}
    for action in CorporateAction.objects.filter(
        asset_id__in=ids, kind=CorporateAction.Kind.SPLIT
    ):
        grouped.setdefault(action.asset_id, []).append(action)
    return grouped


def factor_after(splits: list[CorporateAction] | None, executed_at: datetime) -> Decimal:
    """Product of split factors effective strictly after ``executed_at``.

    A trade on/after a split's effective date is already in post-split terms, so
    only splits dated after the trade adjust it.
    """
    if not splits:
        return Decimal("1")
    trade_date = executed_at.date()
    factor = Decimal("1")
    for action in splits:
        if action.effective_date > trade_date:
            factor *= action.factor
    return factor


def adjusted_quantity_price(
    txn: Transaction, splits: list[CorporateAction] | None
) -> tuple[Decimal, Decimal]:
    """Return ``(quantity, price)`` for ``txn`` in today's post-split terms.

    Cost basis (quantity × price) is preserved; only the share count and per-unit
    price shift. With no applicable split this returns the trade's own values.
    """
    factor = factor_after(splits, txn.executed_at)
    if factor == Decimal("1"):
        return txn.quantity, txn.price
    return txn.quantity * factor, txn.price / factor
