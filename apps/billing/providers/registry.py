"""Provider registry — maps ``settings.BILLING_PROVIDER`` to an implementation.

Real providers (YooKassa for RU, Stripe internationally) implement
``PaymentProvider`` and register here once their API keys are configured. Until
then ``dev`` drives the full flow locally.
"""
from __future__ import annotations

import logging

from django.conf import settings

from .base import PaymentProvider
from .dev import DevProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[PaymentProvider]] = {
    "dev": DevProvider,
    # "yookassa": YooKassaProvider,  # add when keys exist
    # "stripe": StripeProvider,
}


def get_provider(name: str | None = None) -> PaymentProvider:
    """Return the configured provider instance (falls back to dev if unknown)."""
    key = (name or settings.BILLING_PROVIDER or "dev").lower()
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        logger.warning("Unknown billing provider %r; falling back to dev", key)
        provider_cls = DevProvider
    return provider_cls()
