"""YooKassa payment provider — checkout + webhook verification (Tier 4)."""
import json
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import requests
from django.urls import reverse

from apps.billing.providers import get_provider
from apps.billing.providers.yookassa import YooKassaProvider


def _resp(payload):
    return Mock(json=Mock(return_value=payload), raise_for_status=Mock(return_value=None))


def _with_keys(settings):
    settings.YOOKASSA_SHOP_ID = "shop_1"
    settings.YOOKASSA_SECRET_KEY = "secret_1"


def test_registry_resolves_yookassa():
    assert isinstance(get_provider("yookassa"), YooKassaProvider)


@patch("apps.billing.providers.yookassa.requests.post")
def test_create_checkout_builds_payment_and_returns_url(post, settings):
    _with_keys(settings)
    post.return_value = _resp(
        {"id": "pay_1", "confirmation": {"confirmation_url": "https://yoo/checkout/pay_1"}}
    )

    session = YooKassaProvider().create_checkout(
        user_id=7, amount=Decimal("499"), currency="RUB",
        purpose="SUBSCRIPTION", success_url="https://app/return",
    )

    assert session.url == "https://yoo/checkout/pay_1"
    assert session.provider_session_id == "pay_1"
    body = post.call_args.kwargs["json"]
    assert body["amount"] == {"value": "499.00", "currency": "RUB"}
    assert body["metadata"]["user_id"] == "7"
    assert "Idempotence-Key" in post.call_args.kwargs["headers"]


def test_create_checkout_without_keys_raises(settings):
    settings.YOOKASSA_SHOP_ID = ""
    settings.YOOKASSA_SECRET_KEY = ""
    with pytest.raises(RuntimeError):
        YooKassaProvider().create_checkout(
            user_id=1, amount=Decimal("499"), currency="RUB",
            purpose="SUBSCRIPTION", success_url="https://app/return",
        )


@patch("apps.billing.providers.yookassa.requests.get")
def test_webhook_activates_only_when_api_confirms_succeeded(get, settings):
    _with_keys(settings)
    get.return_value = _resp({"status": "succeeded", "metadata": {"user_id": "7"}})
    body = json.dumps({"event": "payment.succeeded", "object": {"id": "pay_1"}}).encode()

    event = YooKassaProvider().parse_webhook(headers={}, body=body)

    assert event is not None
    assert event.type == "payment.succeeded"  # activates Pro
    assert event.user_id == 7
    assert event.payment_id == "pay_1"
    assert event.event_id == "payment.succeeded:pay_1"


@patch("apps.billing.providers.yookassa.requests.get")
def test_webhook_does_not_activate_on_spoofed_status(get, settings):
    _with_keys(settings)
    # The notification claims success, but the API says it's still pending.
    get.return_value = _resp({"status": "pending", "metadata": {"user_id": "7"}})
    body = json.dumps({"event": "payment.succeeded", "object": {"id": "pay_1"}}).encode()

    event = YooKassaProvider().parse_webhook(headers={}, body=body)

    assert event.type != "payment.succeeded"  # not an activating event


@patch("apps.billing.providers.yookassa.requests.get")
def test_webhook_rejected_when_payment_unverifiable(get, settings):
    _with_keys(settings)
    get.side_effect = requests.RequestException("boom")
    body = json.dumps({"event": "payment.succeeded", "object": {"id": "pay_1"}}).encode()

    assert YooKassaProvider().parse_webhook(headers={}, body=body) is None


def test_webhook_rejects_bad_body():
    assert YooKassaProvider().parse_webhook(headers={}, body=b"not json") is None


def test_webhook_rejects_missing_id():
    body = json.dumps({"event": "payment.succeeded", "object": {}}).encode()
    assert YooKassaProvider().parse_webhook(headers={}, body=body) is None


@pytest.mark.django_db
def test_offer_page_renders(client):
    resp = client.get(reverse("offer"))
    assert resp.status_code == 200
    assert "Публичная оферта".encode() in resp.content
