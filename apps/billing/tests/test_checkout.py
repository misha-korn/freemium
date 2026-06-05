"""Upgrade → checkout → dev-confirm → Pro flow, and cancellation (Stage 4)."""
import pytest
from django.urls import reverse

from apps.billing import subscriptions
from apps.billing.models import Payment


@pytest.mark.django_db
def test_upgrade_creates_pending_payment_and_redirects(auth_client, user):
    resp = auth_client.post(reverse("billing:upgrade"))
    assert resp.status_code == 302

    payment = Payment.objects.get(user=user)
    assert payment.status == Payment.Status.PENDING
    assert payment.purpose == Payment.Purpose.SUBSCRIPTION
    # Dev provider sends the user to the internal confirm page.
    assert reverse("billing:dev_confirm", kwargs={"payment_id": payment.id}) in resp.url


@pytest.mark.django_db
def test_upgrade_requires_login(client):
    resp = client.post(reverse("billing:upgrade"))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url


@pytest.mark.django_db
def test_dev_confirm_activates_pro(auth_client, user):
    auth_client.post(reverse("billing:upgrade"))
    payment = Payment.objects.get(user=user)

    resp = auth_client.post(
        reverse("billing:dev_confirm", kwargs={"payment_id": payment.id})
    )
    assert resp.status_code == 302

    payment.refresh_from_db()
    assert payment.status == Payment.Status.SUCCEEDED
    assert subscriptions.is_pro(user) is True


@pytest.mark.django_db
def test_dev_confirm_requires_ownership(auth_client, other_user):
    foreign = Payment.objects.create(
        user=other_user, amount=499, currency="RUB", provider="dev",
        purpose=Payment.Purpose.SUBSCRIPTION, status=Payment.Status.PENDING,
    )
    resp = auth_client.post(
        reverse("billing:dev_confirm", kwargs={"payment_id": foreign.id})
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_dev_confirm_blocked_for_real_provider(auth_client, user, settings):
    auth_client.post(reverse("billing:upgrade"))
    payment = Payment.objects.get(user=user)
    # In production with a real provider, the simulate-payment page must not exist.
    settings.BILLING_PROVIDER = "yookassa"
    resp = auth_client.post(
        reverse("billing:dev_confirm", kwargs={"payment_id": payment.id})
    )
    assert resp.status_code == 404
    assert subscriptions.is_pro(user) is False


@pytest.mark.django_db
def test_cancel_downgrades(auth_client, user):
    subscriptions.activate_pro(user, provider="dev")
    assert subscriptions.is_pro(user) is True

    resp = auth_client.post(reverse("billing:cancel"))
    assert resp.status_code == 302
    assert subscriptions.is_pro(user) is False
