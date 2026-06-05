"""Dev payment provider — simulates checkout and signed webhooks.

Drives the entire upgrade → Pro → webhook flow locally with **no API keys and no
real money**. Checkout "redirects" to an internal confirm page; webhooks are
authenticated with the same HMAC scheme a real provider would use, so the
production code path (verify → activate) is exercised honestly in tests.
"""
from __future__ import annotations

import hmac
import json
import logging
import time
from decimal import Decimal

from django.conf import settings

from .base import CheckoutSession, PaymentProvider, ProviderEvent, sign

logger = logging.getLogger(__name__)


class DevProvider(PaymentProvider):
    name = "dev"

    def create_checkout(
        self,
        *,
        user_id: int,
        amount: Decimal,
        currency: str,
        purpose: str,
        success_url: str,
    ) -> CheckoutSession:
        session_id = f"dev_{user_id}_{int(time.time())}"
        logger.info(
            "DevProvider checkout: %s %s (%s) for user %s -> %s",
            amount,
            currency,
            purpose,
            user_id,
            success_url,
        )
        return CheckoutSession(url=success_url, provider_session_id=session_id)

    def parse_webhook(self, *, headers: dict, body: bytes) -> ProviderEvent | None:
        signature = (
            headers.get("X-Webhook-Signature")
            or headers.get("HTTP_X_WEBHOOK_SIGNATURE")
            or ""
        )
        if not signature:
            return None
        expected = sign(body, settings.BILLING_WEBHOOK_SECRET)
        if not hmac.compare_digest(signature, expected):
            logger.warning("DevProvider webhook signature mismatch")
            return None

        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return None

        event_id = str(payload.get("id") or payload.get("event_id") or "")
        if not event_id:
            return None

        user_id = payload.get("user_id")
        return ProviderEvent(
            event_id=event_id,
            type=str(payload.get("type") or ""),
            user_id=int(user_id) if user_id is not None else None,
            payment_id=str(payload.get("payment_id") or ""),
            raw=payload,
        )
