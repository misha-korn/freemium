"""Forms for market-data price alerts (Stage 5)."""
from __future__ import annotations

from django import forms

from apps.portfolio.models import Asset

from .models import PriceAlert


class PriceAlertForm(forms.ModelForm):
    class Meta:
        model = PriceAlert
        fields = ["asset", "direction", "threshold"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = Asset.objects.all()
