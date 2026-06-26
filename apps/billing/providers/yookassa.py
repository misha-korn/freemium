"""YooKassa payment provider (RU) — Tier 4.

Implements the real upgrade flow against the YooKassa API v3:

- ``create_checkout`` creates a payment and returns its hosted confirmation URL.
- ``parse_webhook`` does NOT trust the webhook body. YooKassa notifications are
  unsigned, so we re-fetch the payment from the API by its id and trust the
  **API's** status — a spoofed notification can't make us activate Pro because
  the API won't confirm a payment that didn't really succeed for our shop.

Credentials come from ``YOOKASSA_SHOP_ID`` / ``YOOKASSA_SECRET_KEY`` (Basic auth);
no secrets are hardcoded. Money is Decimal — formatted to 2dp for the API.
"""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from urllib.parse import quote

import requests
from django.conf import settings

from .base import CheckoutSession, PaymentProvider, ProviderEvent

logger = logging.getLogger(__name__)

API_BASE = "https://api.yookassa.ru/v3"
REQUEST_TIMEOUT = 15
# YooKassa event -> our internal event type. "payment.succeeded" is what the
# webhook view activates on; anything else is passed through and ignored.
_SUCCEEDED = "payment.succeeded"


class YooKassaProvider(PaymentProvider):
    name = "yookassa"

    def __init__(self, shop_id: str | None = None, secret_key: str | None = None) -> None:
        self.shop_id = shop_id if shop_id is not None else getattr(settings, "YOOKASSA_SHOP_ID", "")
        self.secret_key = (
            secret_key if secret_key is not None else getattr(settings, "YOOKASSA_SECRET_KEY", "")
        )

    @property
    def _auth(self) -> tuple[str, str]:
        return (self.shop_id, self.secret_key)

    def create_checkout(
        self,
        *,
        user_id: int,
        amount: Decimal,
        currency: str,
        purpose: str,
        success_url: str,
    ) -> CheckoutSession:
        if not (self.shop_id and self.secret_key):
            raise RuntimeError("YooKassa credentials are not configured")
        body = {
            "amount": {"value": f"{amount:.2f}", "currency": currency},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": success_url},
            "description": f"Freemium Pro ({purpose})",
            # Echoed back on the webhook so we can map the payment to a user.
            "metadata": {"user_id": str(user_id), "purpose": purpose},
        }
        response = requests.post(
            f"{API_BASE}/payments",
            json=body,
            auth=self._auth,
            headers={"Idempotence-Key": uuid.uuid4().hex},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        confirmation_url = (data.get("confirmation") or {}).get("confirmation_url")
        payment_id = data.get("id")
        if not confirmation_url or not payment_id:
            raise RuntimeError("YooKassa did not return a confirmation URL")
        return CheckoutSession(url=confirmation_url, provider_session_id=payment_id)

    def parse_webhook(self, *, headers: dict, body: bytes) -> ProviderEvent | None:
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return None
        event = str(payload.get("event") or "")
        obj = payload.get("object") or {}
        payment_id = str(obj.get("id") or "")
        if not event or not payment_id:
            return None

        # Trust the API, not the (unsigned) notification body.
        payment = self._fetch_payment(payment_id)
        if payment is None:
            logger.warning("YooKassa: could not verify payment %s; rejecting", payment_id)
            return None

        status = str(payment.get("status") or "")
        metadata = payment.get("metadata") or {}
        user_id = metadata.get("user_id")
        # Only a payment the API confirms as succeeded activates Pro.
        event_type = _SUCCEEDED if status == "succeeded" else f"payment.{status or 'unknown'}"
        return ProviderEvent(
            # One action per payment+event; the webhook view dedups on this.
            event_id=f"{event}:{payment_id}",
            type=event_type,
            user_id=int(user_id) if user_id is not None else None,
            payment_id=payment_id,
            raw=payload,
        )

    def _fetch_payment(self, payment_id: str) -> dict | None:
        if not (self.shop_id and self.secret_key):
            return None
        try:
            response = requests.get(
                f"{API_BASE}/payments/{quote(payment_id, safe='')}",
                auth=self._auth,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("YooKassa payment fetch failed (%s): %s", payment_id, exc)
            return None
