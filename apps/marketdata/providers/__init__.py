"""Quote provider abstraction.

A single ``QuoteProvider`` interface with market-specific implementations
(MOEX for the Russian market, Finnhub for international) lets the rest of the
app fetch prices without caring where they come from. See ``registry.get_provider``.
"""
from .base import Quote, QuoteProvider
from .registry import get_provider

__all__ = ["Quote", "QuoteProvider", "get_provider"]
