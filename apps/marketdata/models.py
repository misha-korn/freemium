"""Market-data models.

Money rule: price is a DecimalField — never FloatField.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class PriceQuote(models.Model):
    """A single price observation for an asset at a point in time.

    Populated from external providers via Celery from Stage 2 onward. The
    (asset, as_of, source) uniqueness keeps idempotent refreshes from
    duplicating rows.
    """

    asset = models.ForeignKey(
        "portfolio.Asset",
        on_delete=models.CASCADE,
        related_name="quotes",
    )
    # Decimal only — never FloatField for money.
    price = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.CharField(max_length=3)
    as_of = models.DateTimeField()
    source = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of"]
        indexes = [models.Index(fields=["asset", "-as_of"])]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "as_of", "source"],
                name="uniq_quote_asset_asof_source",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source} {self.price} {self.currency} @ {self.as_of:%Y-%m-%d %H:%M}"


class PriceAlert(models.Model):
    """A user's price trigger for an asset — fires once, then deactivates."""

    class Direction(models.TextChoices):
        ABOVE = "ABOVE", "Rises to or above"
        BELOW = "BELOW", "Falls to or below"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="price_alerts",
    )
    asset = models.ForeignKey(
        "portfolio.Asset",
        on_delete=models.CASCADE,
        related_name="price_alerts",
    )
    # Decimal only — never FloatField for money.
    threshold = models.DecimalField(max_digits=20, decimal_places=8)
    direction = models.CharField(max_length=5, choices=Direction.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["asset", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user} {self.asset} {self.direction} {self.threshold}"


class AssetDividend(models.Model):
    """A real, per-share dividend record for an asset, from a market provider.

    Global reference data (like ``PriceQuote``): the **per-share** amount paid on
    an ex-date, fetched from Twelve Data (international) or MOEX ISS (RU). Used to
    auto-import a user's dividend history (per-share × shares held on the date)
    and, later, to estimate forward income. Money rule: amount is Decimal.
    """

    asset = models.ForeignKey(
        "portfolio.Asset",
        on_delete=models.CASCADE,
        related_name="dividend_records",
    )
    ex_date = models.DateField()
    # Per-share amount in `currency`. Decimal only — never FloatField.
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.CharField(max_length=3)
    source = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ex_date"]
        indexes = [models.Index(fields=["asset", "-ex_date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "ex_date", "source"],
                name="uniq_dividend_asset_exdate_source",
            )
        ]

    def __str__(self) -> str:
        return f"{self.asset} {self.amount} {self.currency} ex {self.ex_date}"
