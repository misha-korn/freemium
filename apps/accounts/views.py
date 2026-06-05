"""Account-area views (profile, subscription overview)."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView

from .forms import ProfileForm
from .models import Subscription


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["subscription"] = Subscription.objects.filter(
            user=self.request.user
        ).first()
        return ctx


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = "accounts/profile_form.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset: Any = None):
        return self.request.user

    def form_valid(self, form: ProfileForm):
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)


class SubscriptionView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/subscription.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["subscription"] = Subscription.objects.filter(
            user=self.request.user
        ).first()
        ctx["pro_price"] = settings.PRO_PRICE_AMOUNT
        ctx["pro_currency"] = settings.PRO_PRICE_CURRENCY
        return ctx
