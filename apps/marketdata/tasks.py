"""Celery tasks for market data (Stage 2).

``refresh_active_quotes`` is the periodic entry point (see CELERY_BEAT_SCHEDULE):
it fans out one ``refresh_quote`` per held asset so a slow/failing provider on
one asset cannot block the others.

Model imports are deferred into the task bodies so importing this module during
Celery's ``autodiscover_tasks`` never touches the app registry too early.
"""
from __future__ import annotations

import logging

from celery import shared_task

from .services import fetch_and_store_quote

logger = logging.getLogger(__name__)


@shared_task
def refresh_quote(asset_id: int) -> dict | None:
    """Fetch a fresh quote for one asset and persist a ``PriceQuote``.

    Returns a small JSON-serialisable summary (Celery results must be JSON) or
    None when the asset is gone or no quote is available.
    """
    from apps.portfolio.models import Asset

    try:
        asset = Asset.objects.get(pk=asset_id)
    except Asset.DoesNotExist:
        logger.warning("refresh_quote: asset_id=%s no longer exists", asset_id)
        return None

    price_quote = fetch_and_store_quote(asset)
    if price_quote is None:
        return None
    return {
        "asset_id": asset_id,
        "price": str(price_quote.price),
        "currency": price_quote.currency,
        "source": price_quote.source,
    }


@shared_task
def refresh_active_quotes() -> int:
    """Refresh quotes for every asset referenced by at least one transaction.

    Dispatches one ``refresh_quote`` subtask per asset and returns the count.
    Under ``CELERY_TASK_ALWAYS_EAGER`` (dev/tests) the subtasks run inline.
    """
    from apps.portfolio.models import Asset

    asset_ids = list(
        Asset.objects.filter(transactions__isnull=False)
        .distinct()
        .values_list("id", flat=True)
    )
    for asset_id in asset_ids:
        refresh_quote.delay(asset_id)

    logger.info("refresh_active_quotes dispatched %d asset(s)", len(asset_ids))
    return len(asset_ids)
