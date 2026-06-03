"""Celery tasks for notifications (skeletons; scheduled in Stage 5)."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_daily_digest() -> None:
    """Stage 5: compile and email each user's daily portfolio digest."""
    logger.info("send_daily_digest skeleton invoked")
