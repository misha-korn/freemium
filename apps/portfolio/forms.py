"""Portfolio forms for manual trade entry (Stage 1)."""
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Asset, DividendPayment, Portfolio, Transaction


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
