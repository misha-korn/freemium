from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Subscription


@pytest.mark.django_db
def test_is_pro_matrix(user):
    sub = user.subscription  # auto-created FREE by signal

    assert sub.is_pro is False  # free plan

    sub.plan = Subscription.Plan.PRO
    sub.status = Subscription.Status.ACTIVE
    sub.current_period_end = None
    assert sub.is_pro is True  # pro, active, no expiry

    sub.status = Subscription.Status.CANCELED
    assert sub.is_pro is False  # canceled

    sub.status = Subscription.Status.ACTIVE
    sub.current_period_end = timezone.now() - timedelta(days=1)
    assert sub.is_pro is False  # expired period

    sub.current_period_end = timezone.now() + timedelta(days=1)
    assert sub.is_pro is True  # active future period
