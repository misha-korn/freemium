"""Market-data service layer.

Thin, cached wrapper over the provider abstraction so the rest of the app has a
stable call site. Celery-driven periodic refresh + PriceQuote persistence are
added in Stage 2.
"""
from __future__ import annotations

import logging

from django.core.cache import cache

from .providers.base import Quote
from .providers.registry import get_provider

logger = logging.getLogger(__name__)

QUOTE_CACHE_TTL = 60  # seconds; Stage 2 tunes per market.


def get_cached_quote(market: str, symbol: str) -> Quote | None:
    """Return a live quote, using the cache to avoid hammering providers."""
    cache_key = f"quote:{market}:{symbol}".upper()
    cached: Quote | None = cache.get(cache_key)
    if cached is not None:
        return cached

    quote = get_provider(market).get_quote(symbol)
    if quote is not None:
        cache.set(cache_key, quote, QUOTE_CACHE_TTL)
    return quote
