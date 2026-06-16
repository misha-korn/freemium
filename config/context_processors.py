"""Project-wide template context processors."""
from __future__ import annotations

from django.conf import settings


def static_version(request) -> dict:
    """Expose ``STATIC_VERSION`` for cache-busting CSS/JS query strings.

    In dev this changes on every server start (so a restart always re-fetches
    edited CSS/JS); in prod it's a fixed value (and WhiteNoise already hashes
    filenames, so this is just belt-and-suspenders).
    """
    return {"STATIC_VERSION": settings.STATIC_VERSION}


def notifications(request) -> dict:
    """Expose the unread-notification count for the nav badge (0 for guests)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unread_notifications": 0}
    # Local import keeps settings import light and avoids app-loading order issues.
    from apps.notifications.services import unread_count

    return {"unread_notifications": unread_count(user)}
