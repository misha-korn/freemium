"""Subscription service — Stage 4.

The single place that knows how a paid plan is activated, cancelled, and what a
plan is allowed to do. Views and webhooks call these helpers instead of poking
at ``Subscription`` directly, so plan rules live in one tested module.
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Subscription

if TYPE_CHECKING:
    from apps.accounts.models import User


def _get_or_create(user: User) -> Subscription:
    sub, _ = Subscription.objects.get_or_create(
        user=user, defaults={"plan": Subscription.Plan.FREE}
    )
    return sub


def activate_pro(
    user: User,
    *,
    provider: str,
    provider_subscription_id: str = "",
    period_days: int | None = None,
) -> Subscription:
    """Mark the user as Pro and (re)set the paid period.

    Renewals stack: if there's an unexpired period, we extend from its end rather
    than from now, so paying early never loses days.
    """
    days = settings.PRO_PERIOD_DAYS if period_days is None else period_days
    now = timezone.now()
    sub = _get_or_create(user)

    anchor = (
        sub.current_period_end
        if sub.current_period_end and sub.current_period_end > now
        else now
    )
    sub.plan = Subscription.Plan.PRO
    sub.status = Subscription.Status.ACTIVE
    sub.provider = provider
    if provider_subscription_id:
        sub.provider_subscription_id = provider_subscription_id
    sub.current_period_end = anchor + timedelta(days=days)
    sub.save()
    return sub


def cancel(user: User) -> Subscription:
    """Cancel the subscription (access ends immediately for this MVP).

    Real providers usually grant access until the period end and notify via a
    later webhook; we keep it simple and revoke now. ``current_period_end`` is
    retained for the record.
    """
    sub = _get_or_create(user)
    sub.status = Subscription.Status.CANCELED
    sub.save(update_fields=["status", "updated_at"])
    return sub


def is_pro(user: User) -> bool:
    """True if the user currently has active Pro access."""
    sub = Subscription.objects.filter(user=user).first()
    return bool(sub and sub.is_pro)


def portfolio_limit(user: User) -> int | None:
    """Max portfolios allowed for this user, or None when unlimited (Pro)."""
    if is_pro(user):
        return None
    return settings.FREE_MAX_PORTFOLIOS


def can_create_portfolio(user: User) -> bool:
    """Whether the user may create another portfolio under their plan."""
    limit = portfolio_limit(user)
    if limit is None:
        return True
    return user.portfolios.count() < limit


def remaining_portfolio_slots(user: User) -> int | None:
    """Portfolios the user can still create, or None when unlimited (Pro)."""
    limit = portfolio_limit(user)
    if limit is None:
        return None
    return max(0, limit - user.portfolios.count())
