import pytest
from django.urls import reverse

from apps.portfolio.models import Asset, Portfolio, Transaction


@pytest.mark.django_db
def test_list_requires_login(client):
    resp = client.get(reverse("portfolio:list"))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url


@pytest.mark.django_db
def test_owner_cannot_see_others_portfolio(auth_client, other_user):
    foreign = Portfolio.objects.create(
        owner=other_user, name="Theirs", base_currency="USD"
    )
    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_create_portfolio_sets_owner(auth_client, user):
    resp = auth_client.post(
        reverse("portfolio:create"),
        {"name": "My PF", "base_currency": "USD", "description": ""},
    )
    assert resp.status_code == 302
    assert Portfolio.objects.filter(owner=user, name="My PF").exists()


@pytest.mark.django_db
def test_add_transaction_flow(auth_client, user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": portfolio.pk}),
        {
            "asset": asset.pk,
            "kind": "BUY",
            "quantity": "10",
            "price": "100",
            "fee": "1",
            "executed_at": "2024-01-01T10:00",
            "note": "",
        },
    )
    assert resp.status_code == 302
    assert Transaction.objects.filter(portfolio=portfolio, asset=asset).count() == 1


@pytest.mark.django_db
def test_reject_invalid_quantity(auth_client, user):
    asset = Asset.objects.create(
        ticker="MSFT", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    resp = auth_client.post(
        reverse("portfolio:transaction_create", kwargs={"pk": portfolio.pk}),
        {
            "asset": asset.pk,
            "kind": "BUY",
            "quantity": "0",
            "price": "100",
            "fee": "0",
            "executed_at": "2024-01-01T10:00",
            "note": "",
        },
    )
    assert resp.status_code == 200  # re-rendered with error
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
def test_cannot_add_transaction_to_others_portfolio(auth_client, other_user):
    foreign = Portfolio.objects.create(
        owner=other_user, name="Theirs", base_currency="USD"
    )
    resp = auth_client.get(
        reverse("portfolio:transaction_create", kwargs={"pk": foreign.pk})
    )
    assert resp.status_code == 404
