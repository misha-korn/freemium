"""Billing views — public pricing + idempotent webhook intake (Stage 1 stub)."""
from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from .models import WebhookEvent

logger = logging.getLogger(__name__)


class PricingView(TemplateView):
    """Public Free vs Pro pricing page."""

    template_name = "billing/pricing.html"


@csrf_exempt
@require_POST
def webhook(request: HttpRequest, provider: str) -> HttpResponse:
    """Record an incoming payment webhook idempotently and acknowledge.

    SECURITY / TODO (Stage 4): verify the provider signature BEFORE trusting the
    body, then activate/deactivate the user's subscription. For now we only
    persist the event (deduplicated by provider+event_id) and return 200.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    event_id = str(payload.get("id") or payload.get("event_id") or "")
    if not event_id:
        return JsonResponse({"ok": False, "error": "missing event id"}, status=400)

    WebhookEvent.objects.get_or_create(
        provider=provider,
        event_id=event_id,
        defaults={"payload": payload},
    )
    return JsonResponse({"ok": True})
