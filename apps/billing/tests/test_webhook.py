import json

import pytest
from django.urls import reverse

from apps.billing.models import WebhookEvent


@pytest.mark.django_db
def test_webhook_is_idempotent(client):
    url = reverse("billing:webhook", kwargs={"provider": "stripe"})
    body = json.dumps({"id": "evt_1", "type": "payment.succeeded"})

    r1 = client.post(url, data=body, content_type="application/json")
    r2 = client.post(url, data=body, content_type="application/json")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert (
        WebhookEvent.objects.filter(provider="stripe", event_id="evt_1").count() == 1
    )


@pytest.mark.django_db
def test_webhook_rejects_get(client):
    url = reverse("billing:webhook", kwargs={"provider": "stripe"})
    assert client.get(url).status_code == 405


@pytest.mark.django_db
def test_pricing_page_renders(client):
    assert client.get(reverse("billing:pricing")).status_code == 200
