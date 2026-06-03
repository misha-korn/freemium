"""Notification service layer."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.mail import send_mail

from .models import Notification

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)


def notify(
    user: AbstractBaseUser,
    kind: str,
    title: str,
    body: str = "",
) -> Notification:
    """Create an in-app notification record for ``user``."""
    return Notification.objects.create(user=user, kind=kind, title=title, body=body)


def send_email_notification(notification: Notification) -> bool:
    """Best-effort email delivery for a notification. Returns success."""
    email = getattr(notification.user, "email", "")
    if not email:
        return False
    try:
        send_mail(
            subject=notification.title,
            message=notification.body,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[email],
        )
    except Exception as exc:  # noqa: BLE001 - log + report failure, never silent
        logger.warning("Email notification failed for %s: %s", email, exc)
        return False
    return True
