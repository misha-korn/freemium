"""Celery tasks for market data (skeletons; scheduled in Stage 2)."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def refresh_quote(asset_id: int) -> None:
    """Stage 2: fetch a fresh quote for one asset and persist a PriceQuote."""
    logger.info("refresh_quote skeleton invoked for asset_id=%s", asset_id)


@shared_task
def refresh_active_quotes() -> None:
    """Stage 2: refresh quotes for every asset currently held in a portfolio."""
    logger.info("refresh_active_quotes skeleton invoked")
