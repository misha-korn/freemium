"""Billing models.

Money rule: amounts are DecimalField — never FloatField. Real provider
integration (YooKassa / CloudPayments / Stripe) arrives in Stage 4.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Payment(models.Model):
    """A payment attempt/record tied to a user."""

    class Purpose(models.TextChoices):
        SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
        ONE_TIME = "ONE_TIME", "One-time"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    # Decimal only — never FloatField for money.
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.CharField(max_length=3)
    provider = models.CharField(max_length=30)
    provider_payment_id = models.CharField(max_length=255, blank=True)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} {self.amount} {self.currency} ({self.status})"


class WebhookEvent(models.Model):
    """Idempotency log for incoming provider webhooks.

    The (provider, event_id) uniqueness guarantees we process each event once.
    """

    provider = models.CharField(max_length=30)
    event_id = models.CharField(max_length=120)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="uniq_webhook_provider_event",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"
