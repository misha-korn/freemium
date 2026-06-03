import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Subscription


@pytest.mark.django_db
def test_subscription_created_on_user_create():
    new_user = get_user_model().objects.create_user(
        username="zoe", email="zoe@example.com", password="pw-12345!"
    )
    sub = Subscription.objects.get(user=new_user)
    assert sub.plan == Subscription.Plan.FREE
    assert sub.status == Subscription.Status.ACTIVE
