"""Free-plan portfolio limit enforcement (Stage 4)."""
import pytest
from django.urls import reverse

from apps.billing import subscriptions
from apps.portfolio.models import Portfolio


@pytest.mark.django_db
def test_free_user_can_create_first_portfolio(auth_client):
    resp = auth_client.get(reverse("portfolio:create"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_free_user_blocked_at_limit_redirects_to_pricing(auth_client, user, settings):
    settings.FREE_MAX_PORTFOLIOS = 1
    Portfolio.objects.create(owner=user, name="One", base_currency="USD")

    resp = auth_client.get(reverse("portfolio:create"))
    assert resp.status_code == 302
    assert reverse("billing:pricing") in resp.url


@pytest.mark.django_db
def test_free_user_post_at_limit_does_not_create(auth_client, user, settings):
    settings.FREE_MAX_PORTFOLIOS = 1
    Portfolio.objects.create(owner=user, name="One", base_currency="USD")

    resp = auth_client.post(
        reverse("portfolio:create"),
        {"name": "Two", "base_currency": "USD", "description": ""},
    )
    assert resp.status_code == 302
    assert Portfolio.objects.filter(owner=user).count() == 1


@pytest.mark.django_db
def test_pro_user_is_unlimited(auth_client, user, settings):
    settings.FREE_MAX_PORTFOLIOS = 1
    subscriptions.activate_pro(user, provider="dev")
    Portfolio.objects.create(owner=user, name="One", base_currency="USD")

    resp = auth_client.get(reverse("portfolio:create"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_list_exposes_plan_context(auth_client, user, settings):
    settings.FREE_MAX_PORTFOLIOS = 1
    resp = auth_client.get(reverse("portfolio:list"))
    assert resp.context["can_create_portfolio"] is True
    Portfolio.objects.create(owner=user, name="One", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:list"))
    assert resp.context["can_create_portfolio"] is False
