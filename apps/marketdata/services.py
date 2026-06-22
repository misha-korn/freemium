"""Market-data service layer.

A thin, cached wrapper over the provider abstraction plus the Stage 2
persistence helpers: fetch a fresh quote, store it as a ``PriceQuote`` row, and
read the latest stored price(s) for valuation.

Money is Decimal — never float.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.core.cache import cache

from .models import PriceQuote
from .providers.base import Quote, SymbolMatch
from .providers.registry import get_provider

if TYPE_CHECKING:
    from apps.portfolio.models import Asset

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


def store_quote(asset: Asset, quote: Quote) -> PriceQuote:
    """Persist a ``Quote`` as a ``PriceQuote`` row.

    Idempotent on (asset, as_of, source) — the model's unique constraint — so a
    repeated refresh at the same timestamp does not duplicate rows.
    """
    price_quote, created = PriceQuote.objects.get_or_create(
        asset=asset,
        as_of=quote.as_of,
        source=quote.source,
        defaults={"price": quote.price, "currency": quote.currency},
    )
    if created:
        logger.info(
            "Stored quote %s %s for %s", quote.price, quote.currency, asset.ticker
        )
        # Evaluate price alerts only on a genuinely new observation.
        from .alerts import check_price_alerts

        check_price_alerts(asset, quote.price)
    return price_quote


def fetch_and_store_quote(asset: Asset) -> PriceQuote | None:
    """Fetch a fresh quote for ``asset`` from its market provider and persist it.

    Returns the stored ``PriceQuote`` or None when no quote is available (the
    provider failed, returned nothing, or the market is unmapped).
    """
    quote = get_provider(asset.market).get_quote(asset.ticker)
    if quote is None:
        logger.info("No quote available for %s (%s)", asset.ticker, asset.market)
        return None
    return store_quote(asset, quote)


def latest_quote(asset: Asset) -> PriceQuote | None:
    """Return the most recent stored ``PriceQuote`` for an asset, or None.

    Relies on the model's default ``-as_of`` ordering.
    """
    return asset.quotes.first()


def latest_quotes(asset_ids: Iterable[int]) -> dict[int, PriceQuote]:
    """Map each asset id to its newest ``PriceQuote``.

    Portable across SQLite/Postgres (no ``DISTINCT ON``): rows are streamed in
    ``(asset_id, -as_of)`` order and the first seen per asset wins.
    """
    ids = list(dict.fromkeys(asset_ids))  # de-dupe, keep order
    if not ids:
        return {}

    newest: dict[int, PriceQuote] = {}
    rows = PriceQuote.objects.filter(asset_id__in=ids).order_by(
        "asset_id", "-as_of", "-id"
    )
    for quote in rows:
        if quote.asset_id not in newest:
            newest[quote.asset_id] = quote
    return newest


def resolve_asset_name(market: str, ticker: str) -> str | None:
    """Best-effort display name for an instrument from its market provider.

    Returns None when it can't be resolved (unknown ticker, no provider for the
    market, or a network issue) — callers treat the name as optional.
    """
    return get_provider(market).get_name(ticker.strip())


def search_symbols(
    market: str, query: str, asset_type: str | None = None
) -> list[SymbolMatch]:
    """Tradable symbols matching ``query`` on ``market``, narrowed by asset type."""
    query = query.strip()
    if not query:
        return []
    return get_provider(market).search(query, asset_type)
