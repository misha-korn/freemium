"""Tests for the subscription service: activation, cancellation, plan limits."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Subscription
from apps.billing import subscriptions
from apps.portfolio.models import Portfolio


@pytest.mark.django_db
def test_activate_pro_sets_plan_status_and_period(user):
    sub = subscriptions.activate_pro(user, provider="dev", period_days=30)

    assert sub.plan == Subscription.Plan.PRO
    assert sub.status == Subscription.Status.ACTIVE
    assert sub.provider == "dev"
    assert sub.is_pro is True
    assert sub.current_period_end is not None
    # ~30 days out (allow a minute of slack).
    delta = sub.current_period_end - timezone.now()
    assert timedelta(days=29, hours=23) < delta < timedelta(days=30, minutes=1)


@pytest.mark.django_db
def test_activate_pro_extends_existing_period(user):
    sub1 = subscriptions.activate_pro(user, provider="dev", period_days=30)
    first_end = sub1.current_period_end
    # Renewing again pushes the period end further out (stacks from the end).
    sub2 = subscriptions.activate_pro(user, provider="dev", period_days=30)
    assert sub2.current_period_end >= first_end


@pytest.mark.django_db
def test_cancel_reverts_to_non_pro(user):
    active = subscriptions.activate_pro(user, provider="dev", period_days=30)
    assert active.is_pro is True

    sub = subscriptions.cancel(user)
    assert sub.status == Subscription.Status.CANCELED
    assert sub.is_pro is False


@pytest.mark.django_db
def test_portfolio_limit_free_vs_pro(user, settings):
    settings.FREE_MAX_PORTFOLIOS = 1
    assert subscriptions.portfolio_limit(user) == 1  # Free

    subscriptions.activate_pro(user, provider="dev")
    assert subscriptions.portfolio_limit(user) is None  # Pro = unlimited


@pytest.mark.django_db
def test_can_create_portfolio_respects_free_limit(user, settings):
    settings.FREE_MAX_PORTFOLIOS = 1
    assert subscriptions.can_create_portfolio(user) is True

    Portfolio.objects.create(owner=user, name="One", base_currency="USD")
    assert subscriptions.can_create_portfolio(user) is False  # limit reached
    assert subscriptions.remaining_portfolio_slots(user) == 0

    # Upgrading lifts the cap.
    subscriptions.activate_pro(user, provider="dev")
    assert subscriptions.can_create_portfolio(user) is True
    assert subscriptions.remaining_portfolio_slots(user) is None


@pytest.mark.django_db
def test_missing_subscription_treated_as_free(user):
    # Even with no Subscription row, the user is treated as Free (never crashes).
    Subscription.objects.filter(user=user).delete()
    assert subscriptions.portfolio_limit(user) == 1
    assert subscriptions.can_create_portfolio(user) is True
