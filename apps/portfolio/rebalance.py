"""Rebalancing — Tier 2 (#6): target weights + buy/sell suggestions.

Compares each holding's **current** weight (market value in the base currency)
against a user-set **target** weight and suggests how much to buy or sell to
reach it. Suggestions are produced only when the portfolio is fully priced and
every currency converts to the base currency — otherwise we can't weigh holdings
honestly, so we show targets without amounts rather than guess.

Money is Decimal — never float.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.marketdata import fx

from .valuation import portfolio_valuation

if TYPE_CHECKING:
    from .models import Asset, Portfolio

_MONEY = Decimal("0.01")
# Drift below this share of the portfolio is treated as "on target" (no trade),
# so tiny rounding differences don't produce noise suggestions.
_HOLD_BAND = Decimal("0.005")  # 0.5%


@dataclass(frozen=True)
class RebalanceRow:
    """One asset's current vs target weight and the suggested trade."""

    asset: Asset
    current_value: Decimal | None   # base currency, None if unpriced
    current_weight: Decimal | None  # fraction (0.25 == 25%)
    target_weight: Decimal | None   # fraction, None if no target set
    target_percent: Decimal | None  # raw percent for the form input, None if unset
    drift: Decimal | None           # current − target (fraction)
    action: str                     # "BUY" / "SELL" / "HOLD" / ""
    amount: Decimal | None          # base currency to trade (>= 0), None if N/A


def build_rebalance(portfolio: Portfolio, *, rates: dict | None = None) -> dict:
    """Current vs target allocation with buy/sell suggestions.

    Shape::

        {
          "base_currency": str,
          "available": bool,          # suggestions computed (fully priced + FX)
          "total": Decimal | None,    # base-currency market value
          "rows": list[RebalanceRow], # held assets ∪ targeted assets
          "target_sum": Decimal,      # sum of target weights, percent
          "missing_fx": list[str],
        }
    """
    valuation = portfolio_valuation(portfolio, rates=rates)
    base = valuation["base_currency"]
    available = valuation["fully_priced"] and not valuation["missing_fx"]
    total = valuation["totals"]["market_value_base"] if available else None

    targets = {
        target.asset_id: target
        for target in portfolio.rebalance_targets.select_related("asset")
    }

    # Current base-currency value per held asset (None when not fully priced).
    current_value: dict[int, Decimal | None] = {}
    asset_by_id: dict[int, Asset] = {}
    for vp in valuation["positions"]:
        asset_by_id[vp.asset.id] = vp.asset
        current_value[vp.asset.id] = (
            fx.convert(vp.market_value, vp.currency, base, rates) if available else None
        )
    for asset_id, target in targets.items():
        asset_by_id.setdefault(asset_id, target.asset)

    rows = [
        _build_row(asset_by_id[aid], current_value.get(aid), targets.get(aid), total, available)
        for aid in _ordered_ids(current_value, targets)
    ]
    target_sum = sum((t.target_weight for t in targets.values()), Decimal("0"))
    return {
        "base_currency": base,
        "available": available,
        "total": total,
        "rows": rows,
        "target_sum": target_sum,
        "missing_fx": valuation["missing_fx"],
    }


def _ordered_ids(current_value: dict, targets: dict) -> list[int]:
    """Held assets first (de-duped), then any targeted-but-not-held assets."""
    ordered = list(current_value.keys())
    for asset_id in targets:
        if asset_id not in current_value:
            ordered.append(asset_id)
    return ordered


def _build_row(
    asset: Asset,
    current_value: Decimal | None,
    target,
    total: Decimal | None,
    available: bool,
) -> RebalanceRow:
    target_weight = (target.target_weight / Decimal("100")) if target else None

    current_weight = None
    if available and total and total > 0 and current_value is not None:
        current_weight = current_value / total

    drift = None
    action = ""
    amount = None
    if available and total is not None and target_weight is not None:
        held = current_value or Decimal("0")
        target_value = total * target_weight
        delta = target_value - held
        if current_weight is not None:
            drift = current_weight - target_weight
        if abs(delta) <= total * _HOLD_BAND:
            action, amount = "HOLD", Decimal("0.00")
        elif delta > 0:
            action, amount = "BUY", delta.quantize(_MONEY)
        else:
            action, amount = "SELL", (-delta).quantize(_MONEY)

    return RebalanceRow(
        asset=asset,
        current_value=current_value.quantize(_MONEY) if current_value is not None else None,
        current_weight=current_weight,
        target_weight=target_weight,
        target_percent=target.target_weight if target else None,
        drift=drift,
        action=action,
        amount=amount,
    )
