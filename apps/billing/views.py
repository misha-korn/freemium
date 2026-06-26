"""Billing views — pricing, checkout/upgrade, dev confirm, cancel, webhook.

Stage 4: a real upgrade flow behind the provider abstraction. The dev provider
drives it locally; the webhook verifies a signature before trusting anything and
activates Pro idempotently — the same path a real provider would use.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from . import subscriptions
from .models import Payment, WebhookEvent
from .providers import ProviderEvent, get_provider

logger = logging.getLogger(__name__)

# Webhook event types we act on (kept provider-agnostic in the dev provider).
_ACTIVATE_EVENTS = {"payment.succeeded", "subscription.activated"}
_CANCEL_EVENTS = {"subscription.cancelled", "subscription.deleted"}


class PricingView(TemplateView):
    """Public Free vs Pro pricing page."""

    template_name = "billing/pricing.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["pro_price"] = settings.PRO_PRICE_AMOUNT
        ctx["pro_currency"] = settings.PRO_PRICE_CURRENCY
        ctx["billing_enabled"] = settings.BILLING_ENABLED
        if self.request.user.is_authenticated:
            ctx["is_pro"] = subscriptions.is_pro(self.request.user)
        return ctx


class UpgradeView(LoginRequiredMixin, View):
    """Start a Pro checkout: record a PENDING Payment, create a provider session,
    and redirect the user to pay."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Paid checkout is gated behind BILLING_ENABLED. While it's off (no live
        # provider yet) the upgrade is "coming soon": never start a checkout that
        # would dead-end, and guard the endpoint against a direct POST.
        if not settings.BILLING_ENABLED:
            messages.info(request, _("Paid plans are coming soon."))
            return redirect("billing:pricing")
        amount = Decimal(str(settings.PRO_PRICE_AMOUNT))
        currency = settings.PRO_PRICE_CURRENCY
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            currency=currency,
            provider=settings.BILLING_PROVIDER,
            purpose=Payment.Purpose.SUBSCRIPTION,
            status=Payment.Status.PENDING,
        )
        # Where the provider returns the user after paying. The dev provider
        # activates Pro on its confirm page; a real provider (YooKassa) activates
        # via webhook, so it just returns to the subscription page.
        if settings.BILLING_PROVIDER == "dev":
            success_url = request.build_absolute_uri(
                reverse("billing:dev_confirm", kwargs={"payment_id": payment.id})
            )
        else:
            success_url = request.build_absolute_uri(reverse("accounts:subscription"))
        session = get_provider().create_checkout(
            user_id=request.user.id,
            amount=amount,
            currency=currency,
            purpose=payment.purpose,
            success_url=success_url,
        )
        payment.provider_payment_id = session.provider_session_id
        payment.save(update_fields=["provider_payment_id"])
        return redirect(session.url)


class DevConfirmView(LoginRequiredMixin, View):
    """DEV ONLY: simulate the provider's redirect-back after a successful payment.

    Activates Pro directly so the flow is testable without keys. With a real
    provider Pro is activated by the webhook instead, so this page 404s unless
    the dev provider is active — it must never be a free upgrade in production.
    """

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        if settings.BILLING_PROVIDER != "dev":
            raise Http404("dev confirm is only available with the dev provider")
        return super().dispatch(request, *args, **kwargs)

    def get(
        self, request: HttpRequest, payment_id: int, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        return render(request, "billing/dev_confirm.html", {"payment": payment})

    def post(
        self, request: HttpRequest, payment_id: int, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        payment = get_object_or_404(
            Payment,
            id=payment_id,
            user=request.user,
            status=Payment.Status.PENDING,
        )
        payment.status = Payment.Status.SUCCEEDED
        payment.save(update_fields=["status"])
        subscriptions.activate_pro(
            request.user,
            provider=settings.BILLING_PROVIDER,
            provider_subscription_id=payment.provider_payment_id,
        )
        messages.success(request, _("You're on Pro now — thank you!"))
        return redirect("accounts:subscription")


class CancelView(LoginRequiredMixin, View):
    """Cancel the user's subscription (downgrades to Free)."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        subscriptions.cancel(request.user)
        messages.info(request, _("Your subscription was cancelled."))
        return redirect("accounts:subscription")


@csrf_exempt
@require_POST
def webhook(request: HttpRequest, provider: str) -> HttpResponse:
    """Verify, deduplicate and process a provider webhook.

    Security: the signature is verified BEFORE the body is trusted. Idempotency:
    ``(provider, event_id)`` is unique, and a processed event is acknowledged
    without re-acting. Only then do we activate/cancel the subscription.
    """
    event = get_provider(provider).parse_webhook(
        headers=request.headers, body=request.body
    )
    if event is None:
        return JsonResponse(
            {"ok": False, "error": "invalid signature or payload"}, status=400
        )

    record, created = WebhookEvent.objects.get_or_create(
        provider=provider,
        event_id=event.event_id,
        defaults={"payload": event.raw},
    )
    if not created and record.processed:
        return JsonResponse({"ok": True, "deduplicated": True})

    _process_event(provider, event)
    record.processed = True
    record.save(update_fields=["processed"])
    return JsonResponse({"ok": True})


def _process_event(provider: str, event: ProviderEvent) -> None:
    """Apply a verified webhook event to the user's subscription."""
    if event.user_id is None:
        logger.info("Webhook %s has no user_id; ignoring", event.event_id)
        return
    user = get_user_model().objects.filter(id=event.user_id).first()
    if user is None:
        logger.info("Webhook %s references unknown user %s", event.event_id, event.user_id)
        return

    if event.type in _ACTIVATE_EVENTS:
        subscriptions.activate_pro(
            user, provider=provider, provider_subscription_id=event.payment_id
        )
        Payment.objects.filter(
            user=user, provider_payment_id=event.payment_id
        ).update(status=Payment.Status.SUCCEEDED)
    elif event.type in _CANCEL_EVENTS:
        subscriptions.cancel(user)
