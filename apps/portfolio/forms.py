"""Portfolio forms for manual trade entry (Stage 1)."""
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import (
    Asset,
    BondDetail,
    CorporateAction,
    DividendPayment,
    Portfolio,
    Transaction,
)
from .services import held_quantity


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ["name", "base_currency", "description"]
        widgets = {
            "description": forms.TextInput(
                attrs={"placeholder": "Optional — e.g. long-term retirement"}
            ),
        }


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["ticker", "name", "asset_type", "market", "currency", "isin"]
        widgets = {
            # autocomplete=off so the browser's own history popup doesn't fight
            # our custom suggestions dropdown (see static/js/asset_search.js).
            "ticker": forms.TextInput(attrs={"autocomplete": "off"}),
        }
        labels = {
            "ticker": _("Ticker"),
            "name": _("Name"),
            "asset_type": _("Asset type"),
            "market": _("Market"),
            "currency": _("Currency"),
            "isin": _("ISIN"),
        }


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["asset", "kind", "quantity", "price", "fee", "executed_at", "note"]
        widgets = {
            "executed_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }
        labels = {
            "asset": _("Asset"),
            "kind": _("Type"),
            "quantity": _("Quantity"),
            "price": _("Price"),
            "fee": _("Fee"),
            "executed_at": _("Executed at"),
            "note": _("Note"),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        # The view passes the parent portfolio so a SELL can be validated against
        # what's actually held (CreateView assigns it after validation, so the
        # form can't read it from the instance yet).
        self.portfolio: Portfolio | None = kwargs.pop("portfolio", None)
        super().__init__(*args, **kwargs)
        # Accept the value produced by the <input type="datetime-local"> widget.
        self.fields["executed_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]
        self.fields["asset"].queryset = Asset.objects.all()
        self.fields["note"].required = False

    def clean_quantity(self) -> Decimal:
        quantity: Decimal = self.cleaned_data["quantity"]
        if quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean_price(self) -> Decimal:
        price: Decimal = self.cleaned_data["price"]
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def _portfolio(self) -> Portfolio | None:
        """Resolve the portfolio: passed by the view (create) or on the instance (edit)."""
        if self.portfolio is not None:
            return self.portfolio
        if self.instance and self.instance.pk:
            return self.instance.portfolio
        return None

    def clean(self) -> dict:
        """Block selling more units than are held (no negative positions).

        Editing an existing SELL excludes that trade from the tally, so a valid
        sell stays valid on edit. BUYs are never restricted.
        """
        cleaned = super().clean()
        if cleaned.get("kind") != "SELL":
            return cleaned

        quantity = cleaned.get("quantity")
        asset = cleaned.get("asset")
        portfolio = self._portfolio()
        if quantity is None or asset is None or portfolio is None:
            return cleaned

        held = held_quantity(
            portfolio, asset, exclude_id=self.instance.pk if self.instance else None
        )
        if held <= 0:
            self.add_error(
                "quantity",
                _("You don't hold any %(ticker)s in this portfolio to sell.")
                % {"ticker": asset.ticker},
            )
        elif quantity > held:
            self.add_error(
                "quantity",
                _("You can't sell %(qty)s — you only hold %(held)s %(ticker)s.")
                % {"qty": quantity, "held": held, "ticker": asset.ticker},
            )
        return cleaned


class DividendForm(forms.ModelForm):
    """Manual entry of a dividend or coupon payment (Tier 1)."""

    class Meta:
        model = DividendPayment
        fields = ["asset", "kind", "amount", "tax_withheld", "currency", "paid_on", "note"]
        widgets = {
            "paid_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        labels = {
            "asset": _("Asset"),
            "kind": _("Type"),
            "amount": _("Gross amount"),
            "tax_withheld": _("Tax withheld"),
            "currency": _("Currency"),
            "paid_on": _("Paid on"),
            "note": _("Note"),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        # Accept the value produced by the <input type="date"> widget.
        self.fields["paid_on"].input_formats = ["%Y-%m-%d"]
        self.fields["asset"].queryset = Asset.objects.all()
        self.fields["note"].required = False
        # Tax is optional; a blank field means "nothing withheld" (see clean).
        self.fields["tax_withheld"].required = False

    def clean_amount(self) -> Decimal:
        amount: Decimal = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError(_("Amount must be greater than zero."))
        return amount

    def clean_tax_withheld(self) -> Decimal:
        tax: Decimal | None = self.cleaned_data.get("tax_withheld")
        if tax is None:
            return Decimal("0")
        if tax < 0:
            raise forms.ValidationError(_("Tax withheld cannot be negative."))
        return tax

    def clean(self) -> dict:
        cleaned = super().clean()
        amount = cleaned.get("amount")
        tax = cleaned.get("tax_withheld") or Decimal("0")
        if amount is not None and tax > amount:
            self.add_error(
                "tax_withheld",
                _("Tax withheld can't exceed the gross amount."),
            )
        return cleaned


class BondDetailForm(forms.ModelForm):
    """Reference details for a bond (face value, coupon, maturity) — Tier 2."""

    class Meta:
        model = BondDetail
        fields = ["face_value", "coupon_rate", "coupon_frequency", "maturity_date"]
        widgets = {
            "maturity_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        labels = {
            "face_value": _("Face value (par)"),
            "coupon_rate": _("Coupon rate, % per year"),
            "coupon_frequency": _("Coupon frequency"),
            "maturity_date": _("Maturity date"),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["maturity_date"].input_formats = ["%Y-%m-%d"]

    def clean_face_value(self) -> Decimal:
        face_value: Decimal = self.cleaned_data["face_value"]
        if face_value <= 0:
            raise forms.ValidationError(_("Face value must be greater than zero."))
        return face_value

    def clean_coupon_rate(self) -> Decimal:
        rate: Decimal = self.cleaned_data["coupon_rate"]
        if rate < 0:
            raise forms.ValidationError(_("Coupon rate cannot be negative."))
        return rate


class CorporateActionForm(forms.ModelForm):
    """Add a stock split for an asset traded in the portfolio — Tier 2 (#7)."""

    class Meta:
        model = CorporateAction
        fields = ["asset", "effective_date", "new_shares", "old_shares", "note"]
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        labels = {
            "asset": _("Asset"),
            "effective_date": _("Effective date"),
            "new_shares": _("New shares"),
            "old_shares": _("Old shares"),
            "note": _("Note"),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        # Scope the asset dropdown to instruments actually traded in this portfolio.
        portfolio = kwargs.pop("portfolio", None)
        super().__init__(*args, **kwargs)
        self.fields["effective_date"].input_formats = ["%Y-%m-%d"]
        self.fields["note"].required = False
        if portfolio is not None:
            self.fields["asset"].queryset = (
                Asset.objects.filter(transactions__portfolio=portfolio).distinct()
            )

    def clean_new_shares(self) -> Decimal:
        value: Decimal = self.cleaned_data["new_shares"]
        if value <= 0:
            raise forms.ValidationError(_("Shares must be greater than zero."))
        return value

    def clean_old_shares(self) -> Decimal:
        value: Decimal = self.cleaned_data["old_shares"]
        if value <= 0:
            raise forms.ValidationError(_("Shares must be greater than zero."))
        return value
