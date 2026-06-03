"""Account signals.

Creates a default FREE ``Subscription`` for every new user automatically.
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Subscription


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_subscription_for_new_user(
    sender: type,
    instance: object,
    created: bool,
    **kwargs: object,
) -> None:
    """Ensure every new user has a FREE Subscription record."""
    if created:
        Subscription.objects.get_or_create(
            user=instance,
            defaults={"plan": Subscription.Plan.FREE},
        )
