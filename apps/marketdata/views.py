"""Price-alert CRUD views (Stage 5)."""
from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView

from .forms import PriceAlertForm
from .models import PriceAlert


class AlertListView(LoginRequiredMixin, ListView):
    template_name = "marketdata/alert_list.html"
    context_object_name = "alerts"

    def get_queryset(self) -> QuerySet[PriceAlert]:
        return self.request.user.price_alerts.select_related("asset")


class AlertCreateView(LoginRequiredMixin, CreateView):
    form_class = PriceAlertForm
    template_name = "marketdata/alert_form.html"
    success_url = reverse_lazy("marketdata:alert_list")

    def form_valid(self, form: PriceAlertForm):
        form.instance.user = self.request.user
        messages.success(self.request, _("Price alert created."))
        return super().form_valid(form)


class AlertDeleteView(LoginRequiredMixin, DeleteView):
    template_name = "marketdata/alert_confirm_delete.html"
    success_url = reverse_lazy("marketdata:alert_list")

    def get_queryset(self) -> QuerySet[PriceAlert]:
        return self.request.user.price_alerts.all()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["alert"] = self.object
        return ctx
