"""Webhook intake: signature verification, idempotency, and activation."""
import json

import pytest
from django.urls import reverse

from apps.billing import subscriptions
from apps.billing.models import Payment, WebhookEvent
from apps.billing.providers import sign

WEBHOOK_URL_PROVIDER = "dev"


def _post_signed(client, payload: dict, secret: str):
    body = json.dumps(payload).encode()
    url = reverse("billing:webhook", kwargs={"provider": WEBHOOK_URL_PROVIDER})
    return client.post(
        url,
        data=body,
        content_type="application/json",
        headers={"X-Webhook-Signature": sign(body, secret)},
    )


@pytest.mark.django_db
def test_webhook_is_idempotent(client, settings):
    settings.BILLING_WEBHOOK_SECRET = "whsec"
    payload = {"id": "evt_1", "type": "info"}

    r1 = _post_signed(client, payload, "whsec")
    r2 = _post_signed(client, payload, "whsec")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert WebhookEvent.objects.filter(provider="dev", event_id="evt_1").count() == 1


@pytest.mark.django_db
def test_webhook_rejects_bad_signature(client, settings):
    settings.BILLING_WEBHOOK_SECRET = "whsec"
    url = reverse("billing:webhook", kwargs={"provider": "dev"})
    body = json.dumps({"id": "evt_2", "type": "payment.succeeded"}).encode()

    resp = client.post(
        url,
        data=body,
        content_type="application/json",
        headers={"X-Webhook-Signature": "deadbeef"},
    )
    assert resp.status_code == 400
    assert WebhookEvent.objects.count() == 0  # nothing trusted/stored


@pytest.mark.django_db
def test_webhook_activates_pro_on_payment_succeeded(client, user, settings):
    settings.BILLING_WEBHOOK_SECRET = "whsec"
    payment = Payment.objects.create(
        user=user, amount=499, currency="RUB", provider="dev",
        provider_payment_id="pay_x", purpose=Payment.Purpose.SUBSCRIPTION,
        status=Payment.Status.PENDING,
    )

    resp = _post_signed(
        client,
        {"id": "evt_3", "type": "payment.succeeded", "user_id": user.id, "payment_id": "pay_x"},
        "whsec",
    )
    assert resp.status_code == 200
    assert subscriptions.is_pro(user) is True
    payment.refresh_from_db()
    assert payment.status == Payment.Status.SUCCEEDED


@pytest.mark.django_db
def test_webhook_cancel_event_downgrades(client, user, settings):
    settings.BILLING_WEBHOOK_SECRET = "whsec"
    subscriptions.activate_pro(user, provider="dev")

    resp = _post_signed(
        client,
        {"id": "evt_4", "type": "subscription.deleted", "user_id": user.id},
        "whsec",
    )
    assert resp.status_code == 200
    assert subscriptions.is_pro(user) is False


@pytest.mark.django_db
def test_webhook_rejects_get(client):
    url = reverse("billing:webhook", kwargs={"provider": "dev"})
    assert client.get(url).status_code == 405


@pytest.mark.django_db
def test_pricing_page_renders(client):
    assert client.get(reverse("billing:pricing")).status_code == 200
