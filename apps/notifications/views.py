"""Notification views — in-app list, mark-read, delivery preferences (Stage 5)."""
from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView, UpdateView

from . import services
from .models import Notification, NotificationPreference


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self) -> QuerySet[Notification]:
        return self.request.user.notifications.all()


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        services.mark_all_read(request.user)
        return redirect("notifications:list")


class PreferencesView(LoginRequiredMixin, UpdateView):
    model = NotificationPreference
    fields = ["email_enabled", "telegram_enabled", "telegram_chat_id"]
    template_name = "notifications/preferences.html"
    success_url = reverse_lazy("notifications:preferences")

    def get_object(self, queryset: Any = None) -> NotificationPreference:
        return services.get_preference(self.request.user)

    def get_form(self, form_class: Any = None) -> Any:
        form = super().get_form(form_class)
        form.fields["email_enabled"].label = _("Email me portfolio digests & alerts")
        form.fields["telegram_enabled"].label = _("Send to Telegram")
        form.fields["telegram_chat_id"].label = _("Telegram chat ID")
        form.fields["telegram_chat_id"].required = False
        return form

    def form_valid(self, form: Any) -> HttpResponse:
        messages.success(self.request, _("Preferences saved."))
        return super().form_valid(form)
