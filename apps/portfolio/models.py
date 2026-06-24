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


# ---------------------------------------------------------------------------
# DividendPayment (Tier 1 — dividends & coupons)
# ---------------------------------------------------------------------------


class DividendPayment(models.Model):
    """A cash income event received within a portfolio.

    Covers a stock/ETF **dividend** or a bond **coupon**. Tier 1 ships manual
    entry first (history + calendar); auto-pulling dividends from MOEX is a
    follow-up. Income figures stay in the payment's own currency and are never
    summed across currencies without an FX rate — same honesty rule as the rest
    of the app.

    Money rule: amount and tax use DecimalField — never FloatField.
    """

    class Kind(models.TextChoices):
        DIVIDEND = "DIVIDEND", _("Dividend")
        COUPON = "COUPON", _("Coupon")

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="dividends",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="dividends",
    )
    kind = models.CharField(
        max_length=8,
        choices=Kind.choices,
        default=Kind.DIVIDEND,
    )
    # Gross amount received for this single payment, in `currency`.
    # Monetary amounts: DecimalField only — never FloatField.
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    # Tax withheld at source (e.g. RU 13% dividend tax). Decimal — never float.
    tax_withheld = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="USD",
    )
    # Pay date — what matters for "income received" history and the calendar.
    paid_on = models.DateField()
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-id"]
        indexes = [models.Index(fields=["portfolio", "-paid_on"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.amount} {self.currency} {self.asset.ticker}"

    @property
    def net_amount(self) -> Decimal:
        """Amount actually received after tax withheld at source."""
        return self.amount - self.tax_withheld


# ---------------------------------------------------------------------------
# PortfolioSnapshot (Tier 1 — value over time)
# ---------------------------------------------------------------------------


class PortfolioSnapshot(models.Model):
    """A daily mark-to-market record of a portfolio's value in base currency.

    The honest answer to "value over time": the current-quote providers give no
    *historical* prices, so rather than back-date today's price onto past
    holdings (dishonest), we record one snapshot per day from now on and let the
    series accumulate. A snapshot is stored **only** when the portfolio is fully
    priced and every currency converts to the base currency — otherwise we'd be
    storing a misleading partial value, so we skip it (see ``snapshots`` service).

    Money rule: market_value and invested use DecimalField — never FloatField.
    """

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    # The calendar date this snapshot represents (one per portfolio per day).
    as_of = models.DateField()
    # Total mark-to-market value in `currency`. Decimal — never float.
    market_value = models.DecimalField(max_digits=20, decimal_places=2)
    # Cumulative net invested capital (cost basis) in `currency`, for context.
    invested = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["as_of"]
        indexes = [models.Index(fields=["portfolio", "as_of"])]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "as_of"],
                name="uniq_snapshot_portfolio_asof",
            )
        ]

    def __str__(self) -> str:
        return f"{self.portfolio} {self.market_value} {self.currency} @ {self.as_of}"


# ---------------------------------------------------------------------------
# BondDetail (Tier 2 — bonds: НКД / coupons / maturity)
# ---------------------------------------------------------------------------


class BondDetail(models.Model):
    """Reference data for a bond ``Asset``: face value, coupon and maturity.

    Manual entry first — accrued coupon (НКД), the next coupon and days to
    maturity are computed locally from these fields (see ``portfolio.bonds``).
    Pricing from the MOEX bonds market is a follow-up increment. Only meaningful
    for BOND-type assets; amounts are in the asset's own currency.

    Money rule: face_value uses DecimalField — never FloatField.
    """

    COUPON_FREQUENCY_CHOICES = [
        (1, _("Annual")),
        (2, _("Semi-annual")),
        (4, _("Quarterly")),
        (12, _("Monthly")),
    ]

    asset = models.OneToOneField(
        Asset,
        on_delete=models.CASCADE,
        related_name="bond",
    )
    # Face value (номинал) per unit, in the asset's currency. Decimal — never float.
    face_value = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0.00000001"))],
    )
    # Annual coupon rate as a percent of face value (e.g. 8.5 == 8.5%/yr).
    coupon_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    coupon_frequency = models.PositiveSmallIntegerField(
        choices=COUPON_FREQUENCY_CHOICES,
        default=2,
    )
    maturity_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.asset.ticker} bond ({self.coupon_rate}% to {self.maturity_date})"

    @property
    def coupon_amount(self) -> Decimal:
        """Coupon paid per unit each period, in the asset's currency."""
        return self.face_value * self.coupon_rate / Decimal("100") / self.coupon_frequency
