"""Payment provider abstraction — Stage 4.

A single interface every provider implements: create a hosted checkout, and
verify + parse an incoming webhook. Concrete providers (dev now; YooKassa/Stripe
once keys exist) live alongside this module. No secrets here.
"""
from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CheckoutSession:
    """Where to send the user to pay, plus the provider's session id."""

    url: str
    provider_session_id: str


@dataclass(frozen=True)
class ProviderEvent:
    """A verified, parsed webhook event.

    Distinct from the ``WebhookEvent`` DB model: this is the in-memory result of
    authenticating and decoding a provider's webhook body.
    """

    event_id: str
    type: str
    user_id: int | None
    payment_id: str
    raw: dict


def sign(body: bytes, secret: str) -> str:
    """HMAC-SHA256 hex signature of a webhook body (used to sign + verify)."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class PaymentProvider(ABC):
    """Abstract payment provider."""

    name: str = "base"

    @abstractmethod
    def create_checkout(
        self,
        *,
        user_id: int,
        amount: Decimal,
        currency: str,
        purpose: str,
        success_url: str,
    ) -> CheckoutSession:
        """Create a hosted checkout session and return where to redirect."""
        raise NotImplementedError

    @abstractmethod
    def parse_webhook(self, *, headers: dict, body: bytes) -> ProviderEvent | None:
        """Verify the signature and parse the event.

        Returns ``None`` when the signature is missing/invalid or the body can't
        be parsed — the caller must treat ``None`` as "reject, do not trust".
        """
        raise NotImplementedError
