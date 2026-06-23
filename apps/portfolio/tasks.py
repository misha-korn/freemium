"""Celery tasks for the portfolio app (Tier 1).

``snapshot_portfolios`` is the periodic entry point (see CELERY_BEAT_SCHEDULE):
once a day it records a mark-to-market ``PortfolioSnapshot`` for every fully
priced portfolio, building the value-over-time series.

The free hosting tier runs no worker, so snapshots are also taken opportunistically
when a priced portfolio is viewed (see ``PortfolioDetailView``); this task is the
belt-and-braces path for deployments that do run Celery Beat.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def snapshot_portfolios() -> int:
    """Record today's value snapshot for every fully priced portfolio."""
    # Deferred import keeps Celery autodiscovery from touching the app registry
    # too early (matches apps.marketdata.tasks).
    from .snapshots import take_all_snapshots

    stored = take_all_snapshots()
    logger.info("snapshot_portfolios stored %d snapshot(s)", stored)
    return stored
