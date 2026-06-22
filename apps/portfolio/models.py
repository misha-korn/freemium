"""Portfolio domain models for Stage 1 — manual trade entry, no live quotes.

Money rule: ALL monetary amounts use DecimalField — NEVER FloatField. Using
floats for money causes rounding errors in financial calculations.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Module-level choices
# ---------------------------------------------------------------------------

CURRENCY_CHOICES = [
    ("RUB", _("Russian Ruble")),
    ("USD", _("US Dollar")),
    ("EUR", _("Euro")),
    ("GBP", _("British Pound")),
    ("CNY", _("Chinese Yuan")),
]

ASSET_TYPE_CHOICES = [
    ("STOCK", _("Stock")),
    ("BOND", _("Bond")),
    ("ETF", _("ETF")),
    ("FUND", _("Mutual Fund")),
    ("CURRENCY", _("Currency")),
    ("CRYPTO", _("Cryptocurrency")),
    ("OTHER", _("Other")),
]

MARKET_CHOICES = [
    ("MOEX", _("Moscow Exchange")),
    ("US", _("US Markets")),
    ("EU", _("European Markets")),
    ("GLOBAL", _("Global")),
    ("OTHER", _("Other")),
]

TRANSACTION_KIND_CHOICES = [
    ("BUY", _("Buy")),
    ("SELL", _("Sell")),
]


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class Portfolio(models.Model):
    """A named collection of assets owned by a single user."""

    # FK to AUTH_USER_MODEL — never import other apps' models directly.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=120)
    # Monetary amounts: DecimalField only — never FloatField.
    base_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="USD",
    )
    description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="uniq_portfolio_owner_name",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("portfolio:detail", kwargs={"pk": self.pk})


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------


class Asset(models.Model):
    """Shared reference table for tradable instruments.

    Stage 1 note: Asset is NOT per-user — it is a global reference table
    that any authenticated user can query or add to. Per-user holdings are
    computed from Transaction records. Stage 2 will add a FK from
    marketdata.Quote to Asset.
    """

    ticker = models.CharField(max_length=32)
    name = models.CharField(max_length=160, blank=True)
    asset_type = models.CharField(max_length=16, choices=ASSET_TYPE_CHOICES)
    market = models.CharField(max_length=16, choices=MARKET_CHOICES)
    # Monetary amounts: DecimalField only — never FloatField.
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="USD")
    isin = models.CharField(max_length=12, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ticker"]
        constraints = [
            models.UniqueConstraint(
                fields=["ticker", "market"],
                name="uniq_asset_ticker_market",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ticker} ({self.market})"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class Transaction(models.Model):
    """A single buy or sell event within a portfolio.

    Money rule: quantity, price, and fee all use DecimalField — never FloatField.
    """

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    # Use "kind" (not "type") to avoid shadowing Python's built-in.
    kind = models.CharField(max_length=4, choices=TRANSACTION_KIND_CHOICES)

    # Monetary amounts: DecimalField only — never FloatField.
    # Quantity: up to 24 digits, 8 decimal places (supports crypto micro-units).
    quantity = models.DecimalField(
        max_digits=24,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    # Price per unit in the asset's denomination currency.
    price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0"))],
    )
    # Trading / brokerage fee in asset currency.
    fee = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal("0"),
    )
    executed_at = models.DateTimeField()
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]

    def __str__(self) -> str:
        return f"{self.kind} {self.quantity} {self.asset.ticker} @ {self.price}"

    @property
    def gross_value(self) -> Decimal:
        """quantity × price, before fees."""
        return self.quantity * self.price

    @property
    def net_value(self) -> Decimal:
        """Total cash impact: BUY adds fee, SELL subtracts fee."""
        if self.kind == "BUY":
            return self.gross_value + self.fee
        return self.gross_value - self.fee
