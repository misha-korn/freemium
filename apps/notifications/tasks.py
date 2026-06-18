"""Celery tasks for notifications (Stage 5)."""
from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .services import build_portfolio_digest, notify_user

logger = logging.getLogger(__name__)


@shared_task
def send_daily_digest() -> int:
    """Send each user with holdings a portfolio digest (in-app + email if opted in).

    Returns the number of digests sent — handy for logging/monitoring.
    """
    users = get_user_model().objects.filter(portfolios__isnull=False).distinct()
    sent = 0
    for user in users:
        body = build_portfolio_digest(user)
        if not body:
            continue
        notify_user(user, kind="DIGEST", title=_("Your portfolio digest"), body=body)
        sent += 1
    logger.info("send_daily_digest sent %s digest(s)", sent)
    return sent
