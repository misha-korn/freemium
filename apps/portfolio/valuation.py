"""Portfolio valuation — Stage 2.

Turns cost-basis positions (``services.compute_positions``) into mark-to-market
values using the latest stored quotes, aggregates them into the portfolio's base
currency (with FX), and derives returns (simple + money-weighted XIRR).

Honesty rules:
- A position without a usable quote is ``priced=False`` with ``None`` values — we
  never invent a price.
- Base-currency totals are produced only when *every* involved currency converts
  to the base currency; otherwise they are ``None`` and ``missing_fx`` lists the
  currencies we could not convert.

``value_positions`` is pure (takes plain data) so it unit-tests without a DB.
All money is Decimal — never float.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.analytics.services import simple_return, xirr
from apps.marketdata import fx
from apps.marketdata.services import latest_quotes

from .services import Position, compute_positions

if TYPE_CHECKING:
    from apps.portfolio.models import Portfolio

logger = logging.getLogger(__name__)

_MONEY = Decimal("0.01")
_PCT = Decimal("0.01")


@dataclass(frozen=True)
class ValuedPosition:
    """A position priced against its latest quote.

    ``market_value``/``unrealised_pnl``/``simple_return`` are in the asset's own
    currency and are ``None`` when no usable quote exists.
    """

    position: Position
    price: Decimal | None
    as_of: datetime | None
    market_value: Decimal | None
    unrealised_pnl: Decimal | None
    simple_return: Decimal | None  # fraction, e.g. 0.15 == +15%

    @property
    def priced(self) -> bool:
        return self.market_value is not None

    @property
    def return_pct(self) -> Decimal | None:
        if self.simple_return is None:
            return None
        return (self.simple_return * 100).quantize(_PCT)

    # --- convenience passthroughs so templates read `pos.<x>` directly ---
    @property
    def asset(self):  # noqa: ANN201 - Django model, see portfolio.models
        return self.position.asset

    @property
    def quantity(self) -> Decimal:
        return self.position.quantity

    @property
    def avg_cost(self) -> Decimal:
        return self.position.avg_cost

    @property
    def invested(self) -> Decimal:
        return self.position.invested

    @property
    def currency(self) -> str:
        return self.position.currency


def value_positions(
    positions: list[Position], prices: dict[int, Any]
) -> list[ValuedPosition]:
    """Price ``positions`` against ``prices`` (keyed by ``asset.id``).

    Each price object must expose ``price`` (Decimal), ``currency`` (str) and
    ``as_of``. A missing price, or one whose currency disagrees with the
    position, yields an unpriced ``ValuedPosition`` (we do not guess).
    """
    valued: list[ValuedPosition] = []
    for pos in positions:
        point = prices.get(pos.asset.id)
        if point is None:
            valued.append(_unpriced(pos))
            continue
        if point.currency != pos.currency:
            logger.warning(
                "Quote currency %s != asset currency %s for %s; skipping price",
                point.currency,
                pos.currency,
                pos.asset.ticker,
            )
            valued.append(_unpriced(pos))
            continue

        market_value = pos.quantity * point.price
        valued.append(
            ValuedPosition(
                position=pos,
                price=point.price,
                as_of=getattr(point, "as_of", None),
                market_value=market_value,
                unrealised_pnl=market_value - pos.invested,
                simple_return=simple_return(pos.invested, market_value),
            )
        )
    return valued


def _unpriced(pos: Position) -> ValuedPosition:
    return ValuedPosition(
        position=pos,
        price=None,
        as_of=None,
        market_value=None,
        unrealised_pnl=None,
        simple_return=None,
    )


def portfolio_valuation(portfolio: Portfolio, *, rates: dict | None = None) -> dict:
    """Full mark-to-market summary for a portfolio.

    Shape::

        {
          "base_currency": str,
          "positions": list[ValuedPosition],
          "by_currency": {cur: {"invested", "market_value", "unrealised_pnl",
                                "simple_return", "priced"}},
          "totals": {"invested_base", "market_value_base", "unrealised_pnl_base",
                     "simple_return", "xirr"},   # base figures None if FX missing
          "missing_prices": list[str],  # tickers without a quote
          "missing_fx": list[str],      # currencies not convertible to base
          "fully_priced": bool,
          "as_of": datetime | None,     # newest quote across positions
        }
    """
    base = portfolio.base_currency
    positions = compute_positions(portfolio)
    prices = latest_quotes(p.asset.id for p in positions)
    valued = value_positions(positions, prices)

    totals, missing_fx = _base_totals(valued, base, rates)
    totals["xirr"] = _portfolio_xirr(
        portfolio, totals["market_value_base"], base, rates
    )

    priced_times = [vp.as_of for vp in valued if vp.as_of is not None]
    return {
        "base_currency": base,
        "positions": valued,
        "by_currency": _aggregate_by_currency(valued),
        "totals": totals,
        "missing_prices": [vp.asset.ticker for vp in valued if not vp.priced],
        "missing_fx": missing_fx,
        "fully_priced": bool(valued) and all(vp.priced for vp in valued),
        "as_of": max(priced_times) if priced_times else None,
    }


def _aggregate_by_currency(valued: list[ValuedPosition]) -> dict[str, dict]:
    """Sum invested / market value per asset currency (no FX involved)."""
    agg: dict[str, dict] = {}
    for vp in valued:
        cur = vp.currency
        bucket = agg.setdefault(
            cur, {"invested": Decimal("0"), "_mv": Decimal("0"), "priced": True}
        )
        bucket["invested"] += vp.invested
        if vp.priced:
            bucket["_mv"] += vp.market_value
        else:
            bucket["priced"] = False

    for bucket in agg.values():
        if bucket["priced"]:
            market_value = bucket.pop("_mv")
            bucket["market_value"] = market_value
            bucket["unrealised_pnl"] = market_value - bucket["invested"]
            bucket["simple_return"] = simple_return(bucket["invested"], market_value)
        else:
            bucket.pop("_mv")
            bucket["market_value"] = None
            bucket["unrealised_pnl"] = None
            bucket["simple_return"] = None
    return agg


def _base_totals(
    valued: list[ValuedPosition], base: str, rates: dict | None
) -> tuple[dict, list[str]]:
    """Aggregate invested / market value into the base currency via FX."""
    invested_base = Decimal("0")
    market_base = Decimal("0")
    invested_ok = True
    market_ok = bool(valued)
    missing_fx: list[str] = []

    for vp in valued:
        cur = vp.currency
        invested_conv = fx.convert(vp.invested, cur, base, rates)
        if invested_conv is None:
            invested_ok = False
            market_ok = False
            if cur not in missing_fx:
                missing_fx.append(cur)
            continue
        invested_base += invested_conv

        if vp.priced:
            mv_conv = fx.convert(vp.market_value, cur, base, rates)
            if mv_conv is None:
                market_ok = False
            else:
                market_base += mv_conv
        else:
            market_ok = False

    totals = {
        "invested_base": invested_base if invested_ok else None,
        "market_value_base": market_base if market_ok else None,
        "unrealised_pnl_base": (
            market_base - invested_base if invested_ok and market_ok else None
        ),
        "simple_return": (
            simple_return(invested_base, market_base)
            if invested_ok and market_ok
            else None
        ),
    }
    return totals, missing_fx


def _portfolio_xirr(
    portfolio: Portfolio,
    market_value_base: Decimal | None,
    base: str,
    rates: dict | None,
) -> float | None:
    """Money-weighted return in base currency, or None if it can't be computed."""
    if not market_value_base or market_value_base <= 0:
        return None

    cashflows: list[tuple[date, Decimal]] = []
    txns = portfolio.transactions.select_related("asset").order_by("executed_at", "id")
    for txn in txns:
        # Sign convention (analytics.xirr): investments negative, proceeds positive.
        signed = -txn.net_value if txn.kind == "BUY" else txn.net_value
        converted = fx.convert(signed, txn.asset.currency, base, rates)
        if converted is None:
            return None
        cashflows.append((txn.executed_at.date(), converted))

    # Terminal inflow: today's market value closes out the open positions.
    cashflows.append((timezone.now().date(), market_value_base))
    if len(cashflows) < 2:
        return None
    try:
        return xirr(cashflows)
    except ValueError:
        logger.info("XIRR did not converge for portfolio %s", portfolio.pk)
        return None


def invested_timeseries(portfolio: Portfolio, *, rates: dict | None = None) -> dict:
    """Cumulative net invested capital over time, in the base currency.

    A buy deploys capital (line rises); a sell returns cash (line falls). This is
    the honest "first chart" for Stage 2: it needs no historical prices. If any
    transaction currency cannot convert to the base currency, ``available`` is
    False and ``points`` is empty (we don't draw a misleading mixed-currency line).
    """
    base = portfolio.base_currency
    txns = portfolio.transactions.select_related("asset").order_by("executed_at", "id")

    points: list[dict[str, str]] = []
    cumulative = Decimal("0")
    for txn in txns:
        delta = txn.net_value if txn.kind == "BUY" else -txn.net_value
        converted = fx.convert(delta, txn.asset.currency, base, rates)
        if converted is None:
            return {"base_currency": base, "points": [], "available": False}
        cumulative += converted
        points.append(
            {
                "date": txn.executed_at.date().isoformat(),
                "invested": str(cumulative.quantize(_MONEY)),
            }
        )
    return {"base_currency": base, "points": points, "available": True}
