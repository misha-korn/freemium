"""Account-level overview — Stage 3.

Aggregates each portfolio's mark-to-market valuation into cards for the
portfolio list, plus an optional combined total. Honesty rule: a combined
total is produced only when *every* portfolio shares one base currency — we
never sum across currencies without an FX rate.

Money is Decimal — never float.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.analytics.services import simple_return

from .valuation import portfolio_valuation

if TYPE_CHECKING:
    from .models import Portfolio


@dataclass(frozen=True)
class PortfolioCard:
    """A portfolio's headline figures, all in its own base currency."""

    portfolio: Portfolio
    currency: str
    invested: Decimal | None
    market_value: Decimal | None
    unrealised_pnl: Decimal | None
    simple_return: Decimal | None
    xirr: float | None
    fully_priced: bool


def build_account_overview(
    portfolios: Iterable[Portfolio], *, rates: dict | None = None
) -> dict:
    """Build per-portfolio cards plus an optional single-currency combined total.

    Shape::

        {
          "cards": list[PortfolioCard],
          "combined": {
              "currency", "invested", "market_value", "unrealised_pnl",
              "simple_return", "portfolio_count"
          } | None,   # None when empty or currencies differ
        }
    """
    cards: list[PortfolioCard] = []
    for portfolio in portfolios:
        valuation = portfolio_valuation(portfolio, rates=rates)
        totals = valuation["totals"]
        cards.append(
            PortfolioCard(
                portfolio=portfolio,
                currency=valuation["base_currency"],
                invested=totals["invested_base"],
                market_value=totals["market_value_base"],
                unrealised_pnl=totals["unrealised_pnl_base"],
                simple_return=totals["simple_return"],
                xirr=totals["xirr"],
                fully_priced=valuation["fully_priced"],
            )
        )
    return {"cards": cards, "combined": _combined(cards)}


def _combined(cards: list[PortfolioCard]) -> dict | None:
    """Sum cards into one total, but only when they share a single currency."""
    currencies = {card.currency for card in cards}
    if len(currencies) != 1:
        return None  # empty, or multiple currencies — don't fabricate a total
    currency = currencies.pop()

    invested = _sum_or_none(card.invested for card in cards)
    market_value = _sum_or_none(card.market_value for card in cards)

    if invested is not None and market_value is not None:
        unrealised_pnl: Decimal | None = market_value - invested
        ret: Decimal | None = simple_return(invested, market_value)
    else:
        unrealised_pnl = None
        ret = None

    return {
        "currency": currency,
        "invested": invested,
        "market_value": market_value,
        "unrealised_pnl": unrealised_pnl,
        "simple_return": ret,
        "portfolio_count": len(cards),
    }


def _sum_or_none(values: Iterable[Decimal | None]) -> Decimal | None:
    """Sum values, or return None if any is missing (so totals stay honest)."""
    total = Decimal("0")
    for value in values:
        if value is None:
            return None
        total += value
    return total
