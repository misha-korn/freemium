"""Payment provider abstraction (skeleton).

Stage 4 implements concrete providers (YooKassa / CloudPayments for RU, Stripe
for international) behind this interface. No secrets or live calls here yet.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CheckoutSession:
    """Where to send the user to pay, plus the provider's session id."""

    url: str
    provider_session_id: str


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
    ) -> CheckoutSession:
        """Create a hosted checkout session and return where to redirect."""
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, *, headers: dict, body: bytes) -> bool:
        """Verify a webhook signature. Stage 4 implements per provider."""
        raise NotImplementedError
