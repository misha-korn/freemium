"""Tests for the payment provider abstraction + dev provider."""
import json
from decimal import Decimal

from apps.billing.providers import get_provider, sign
from apps.billing.providers.base import CheckoutSession, ProviderEvent
from apps.billing.providers.dev import DevProvider


def test_get_provider_defaults_to_dev(settings):
    settings.BILLING_PROVIDER = "dev"
    provider = get_provider()
    assert isinstance(provider, DevProvider)
    assert provider.name == "dev"


def test_get_provider_by_explicit_name():
    assert isinstance(get_provider("dev"), DevProvider)


def test_dev_create_checkout_returns_session():
    provider = DevProvider()
    session = provider.create_checkout(
        user_id=7,
        amount=Decimal("499"),
        currency="RUB",
        purpose="SUBSCRIPTION",
        success_url="/billing/dev/confirm/7/",
    )
    assert isinstance(session, CheckoutSession)
    assert session.url == "/billing/dev/confirm/7/"
    assert session.provider_session_id


def test_dev_parse_webhook_accepts_valid_signature(settings):
    settings.BILLING_WEBHOOK_SECRET = "s3cret"
    body = json.dumps(
        {"id": "evt_1", "type": "payment.succeeded", "user_id": 7, "payment_id": "pay_1"}
    ).encode()
    headers = {"X-Webhook-Signature": sign(body, "s3cret")}

    event = DevProvider().parse_webhook(headers=headers, body=body)
    assert isinstance(event, ProviderEvent)
    assert event.event_id == "evt_1"
    assert event.type == "payment.succeeded"
    assert event.user_id == 7


def test_dev_parse_webhook_rejects_bad_signature(settings):
    settings.BILLING_WEBHOOK_SECRET = "s3cret"
    body = json.dumps({"id": "evt_1", "type": "payment.succeeded"}).encode()
    headers = {"X-Webhook-Signature": "deadbeef"}

    assert DevProvider().parse_webhook(headers=headers, body=body) is None


def test_dev_parse_webhook_rejects_missing_signature():
    body = json.dumps({"id": "evt_1"}).encode()
    assert DevProvider().parse_webhook(headers={}, body=body) is None


def test_sign_is_stable_and_hex():
    sig = sign(b"hello", "key")
    assert sig == sign(b"hello", "key")
    assert all(c in "0123456789abcdef" for c in sig)
