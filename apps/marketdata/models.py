"""Market-data models.

Money rule: price is a DecimalField — never FloatField.
"""
from __future__ import annotations

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
