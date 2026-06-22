"""Portfolio forms for manual trade entry (Stage 1)."""
from __future__ import annotations

from decimal import Decimal

from django import forms

from .models import Asset, Portfolio, Transaction


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
            "ticker": forms.TextInput(
                attrs={"list": "ticker-suggestions", "autocomplete": "off"}
            ),
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
