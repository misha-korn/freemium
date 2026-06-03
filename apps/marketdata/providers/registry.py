"""Map a market code to a concrete quote provider."""
from __future__ import annotations

from .base import QuoteProvider
from .international import FinnhubQuoteProvider, NullQuoteProvider
from .moex import MoexQuoteProvider

# Market codes mirror portfolio.models.MARKET_CHOICES.
_INTERNATIONAL_MARKETS = {"US", "EU", "GLOBAL"}


def get_provider(market: str) -> QuoteProvider:
    """Return the provider for a market code (MOEX / US / EU / GLOBAL / ...)."""
    code = (market or "").upper()
    if code == "MOEX":
        return MoexQuoteProvider()
    if code in _INTERNATIONAL_MARKETS:
        return FinnhubQuoteProvider()
    return NullQuoteProvider()
