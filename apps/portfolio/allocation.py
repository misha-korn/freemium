"""Portfolio allocation breakdowns — Stage 3.

Turns already-valued positions into diversification views: by holding (ticker),
asset class (``asset_type``), currency and market. Everything is expressed in the
portfolio's base currency via the FX converter so a single pie is comparable.

Honesty rules (consistent with ``valuation``):
- Basis is **market value** only when every position is priced; otherwise we fall
  back to **invested capital** (cost basis), which is always known and needs no
  quote. The chosen basis is reported as ``basis`` so the UI can label it.
- A position whose currency cannot convert to the base currency is *excluded*
  from the base-currency breakdown and its currency is listed in ``missing_fx`` —
  we never mix currencies without a rate.

``build_allocation`` is pure (takes plain ``ValuedPosition`` data, no DB), so it
unit-tests without the database. Money is Decimal — never float. The one
exception is ``chart_payload``, which emits float *percentages* purely for
Chart.js; no monetary value is ever a float.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.analytics.services import allocation_by
from apps.marketdata import fx

from .models import ASSET_TYPE_CHOICES, MARKET_CHOICES

if TYPE_CHECKING:
    from .valuation import ValuedPosition

# Code -> human label maps (plain dicts, so no model instance is needed).
_ASSET_TYPE_LABELS = dict(ASSET_TYPE_CHOICES)
_MARKET_LABELS = dict(MARKET_CHOICES)


@dataclass(frozen=True)
class AllocationSlice:
    """One row of a breakdown: a label, its base-currency value and its share."""

    label: str
    value: Decimal  # base currency
    weight: Decimal  # fraction in 0..1


def build_allocation(
    valued: list[ValuedPosition], base_currency: str, *, rates: dict | None = None
) -> dict:
    """Group ``valued`` positions into base-currency allocation breakdowns.

    Shape::

        {
          "base_currency": str,
          "basis": "market" | "invested",
          "total": Decimal | None,          # base-currency total, None if empty
          "available": bool,                # at least one convertible position
          "missing_fx": list[str],          # currencies excluded for lack of FX
          "by_holding":  list[AllocationSlice],
          "by_class":    list[AllocationSlice],   # asset class (asset_type)
          "by_currency": list[AllocationSlice],
          "by_market":   list[AllocationSlice],
        }
    """
    base = base_currency
    fully_priced = bool(valued) and all(vp.priced for vp in valued)
    basis = "market" if fully_priced else "invested"

    rows: list[tuple[ValuedPosition, Decimal]] = []
    missing_fx: list[str] = []
    for vp in valued:
        raw = vp.market_value if basis == "market" else vp.invested
        converted = fx.convert(raw, vp.currency, base, rates)
        if converted is None:
            if vp.currency not in missing_fx:
                missing_fx.append(vp.currency)
            continue
        rows.append((vp, converted))

    total = sum((value for _, value in rows), Decimal("0"))
    available = bool(rows) and total > 0

    return {
        "base_currency": base,
        "basis": basis,
        "total": total if available else None,
        "available": available,
        "missing_fx": missing_fx,
        "by_holding": _group(rows, lambda vp: vp.asset.ticker),
        "by_class": _group(
            rows,
            lambda vp: _ASSET_TYPE_LABELS.get(vp.asset.asset_type, vp.asset.asset_type),
        ),
        "by_currency": _group(rows, lambda vp: vp.currency),
        "by_market": _group(
            rows, lambda vp: _MARKET_LABELS.get(vp.asset.market, vp.asset.market)
        ),
    }


def _group(
    rows: list[tuple[ValuedPosition, Decimal]],
    key: Callable[[ValuedPosition], str],
) -> list[AllocationSlice]:
    """Sum base-currency value per ``key`` and normalise into weighted slices."""
    sums: dict[str, Decimal] = {}
    for vp, value in rows:
        label = key(vp)
        sums[label] = sums.get(label, Decimal("0")) + value

    weights = allocation_by(sums)
    slices = [
        AllocationSlice(label=label, value=value, weight=weights[label])
        for label, value in sums.items()
    ]
    slices.sort(key=lambda s: s.value, reverse=True)
    return slices


def chart_payload(slices: list[AllocationSlice]) -> dict:
    """Shape a breakdown for Chart.js: labels + percentage values.

    Percentages are floats *only* because they feed a chart; all monetary
    figures elsewhere remain Decimal.
    """
    return {
        "labels": [s.label for s in slices],
        "values": [float(s.weight * 100) for s in slices],
    }
