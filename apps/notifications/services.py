"""Notification service layer."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.mail import send_mail

from .models import Notification, NotificationPreference

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


def get_preference(user: AbstractBaseUser) -> NotificationPreference:
    """Return the user's notification preferences, creating defaults if absent."""
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return pref


def notify_user(
    user: AbstractBaseUser,
    kind: str,
    title: str,
    body: str = "",
    *,
    email: bool = True,
) -> Notification:
    """Create an in-app notification and email it when the user opted in."""
    note = notify(user, kind, title, body)
    if email and get_preference(user).email_enabled:
        send_email_notification(note)
    return note


def unread_count(user: AbstractBaseUser) -> int:
    """Number of unread in-app notifications for ``user``."""
    return Notification.objects.filter(user=user, is_read=False).count()


def mark_all_read(user: AbstractBaseUser) -> int:
    """Mark every unread notification read; return how many were updated."""
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


def build_portfolio_digest(user: AbstractBaseUser) -> str | None:
    """A short per-portfolio summary line for the daily digest, or None if empty."""
    from apps.portfolio.overview import build_account_overview

    portfolios = list(user.portfolios.all())
    if not portfolios:
        return None

    lines: list[str] = []
    for card in build_account_overview(portfolios)["cards"]:
        name = card.portfolio.name
        if card.market_value is not None:
            line = f"{name}: {card.market_value:.2f} {card.currency}"
            if card.simple_return is not None:
                line += f" ({card.simple_return * 100:+.1f}%)"
        elif card.invested is not None:
            line = f"{name}: {card.invested:.2f} {card.currency} invested"
        else:
            line = f"{name}: no trades yet"
        lines.append(line)
    return "\n".join(lines)


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
