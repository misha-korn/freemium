"""Account models.

The custom ``User`` is defined here from day one (per the roadmap) so the auth
model can be extended later without a painful swap. Subscription/billing state
is modelled separately (see ``Subscription``).
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Project user.

    Extends Django's ``AbstractUser``. Email is unique because it is an allowed
    login method (see ``ACCOUNT_LOGIN_METHODS``).
    """

    email = models.EmailField("email address", unique=True)

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"

    def __str__(self) -> str:
        return self.get_username()


class Subscription(models.Model):
    """Tracks a user's subscription plan and payment provider state."""

    class Plan(models.TextChoices):
        FREE = "FREE", "Free"
        PRO = "PRO", "Pro"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        TRIALING = "TRIALING", "Trialing"
        PAST_DUE = "PAST_DUE", "Past Due"
        CANCELED = "CANCELED", "Canceled"

    class Provider(models.TextChoices):
        NONE = "NONE", "None"
        YOOKASSA = "YOOKASSA", "YooKassa"
        CLOUDPAYMENTS = "CLOUDPAYMENTS", "CloudPayments"
        STRIPE = "STRIPE", "Stripe"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.NONE)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self) -> str:
        return f"{self.user} — {self.plan}"

    @property
    def is_pro(self) -> bool:
        """Return True if the user has an active Pro subscription."""
        if self.plan != self.Plan.PRO:
            return False
        if self.status not in (self.Status.ACTIVE, self.Status.TRIALING):
            return False
        if self.current_period_end is None:
            return True
        return self.current_period_end > timezone.now()
