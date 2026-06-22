from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.marketdata.models import PriceQuote
from apps.portfolio.models import Asset, Portfolio, Transaction


@pytest.mark.django_db
def test_list_requires_login(client):
    resp = client.get(reverse("portfolio:list"))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url


@pytest.mark.django_db
def test_list_shows_account_overview(auth_client, user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal("10"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    PriceQuote.objects.create(
        asset=asset, price=Decimal("150"), currency="USD",
        as_of=datetime.now(UTC), source="TEST",
    )

    resp = auth_client.get(reverse("portfolio:list"))
    assert resp.status_code == 200
    overview = resp.context["overview"]
    assert overview["combined"]["market_value"] == Decimal("1500")
    assert [c.portfolio.name for c in overview["cards"]] == ["Main"]


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


@pytest.mark.django_db
def test_detail_shows_market_value_when_priced(auth_client, user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal("10"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    PriceQuote.objects.create(
        asset=asset, price=Decimal("150"), currency="USD",
        as_of=datetime.now(UTC), source="TEST",
    )

    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": portfolio.pk}))
    assert resp.status_code == 200
    valuation = resp.context["valuation"]
    assert valuation["totals"]["market_value_base"] == Decimal("1500")
    # Chart series is rendered for a single-currency portfolio.
    assert resp.context["chart_data"]["available"] is True


@pytest.mark.django_db
def test_detail_renders_unpriced_without_error(auth_client, user):
    """Detail page must render cleanly when nothing is priced (None totals)."""
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal("10"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )  # no PriceQuote -> unpriced

    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": portfolio.pk}))
    assert resp.status_code == 200
    assert resp.context["valuation"]["totals"]["market_value_base"] is None


@pytest.mark.django_db
def test_detail_builds_allocation_donuts_across_classes(auth_client, user):
    """A multi-class portfolio exposes a 'by asset class' donut on the dashboard."""
    stock = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    etf = Asset.objects.create(
        ticker="VOO", asset_type="ETF", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Mix", base_currency="USD")
    for asset in (stock, etf):
        Transaction.objects.create(
            portfolio=portfolio, asset=asset, kind="BUY",
            quantity=Decimal("10"), price=Decimal("100"), fee=Decimal("0"),
            executed_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": portfolio.pk}))
    assert resp.status_code == 200

    allocation = resp.context["allocation"]
    assert allocation["available"] is True
    assert {s.label for s in allocation["by_class"]} == {"Stock", "ETF"}

    chart_titles = {c["title"] for c in resp.context["allocation_charts"]}
    assert "By asset class" in chart_titles
    # Single-currency, single-market portfolio: those axes are not charted.
    assert "By currency" not in chart_titles
    assert "By market" not in chart_titles
    # The donut canvas and its JSON data island are present in the HTML.
    assert b'id="donut-class"' in resp.content
    assert b'id="donut-class-data"' in resp.content


@pytest.mark.django_db
def test_detail_no_allocation_charts_for_single_holding(auth_client, user):
    """A single holding has no diversification story — no donuts rendered."""
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Solo", base_currency="USD")
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal("10"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": portfolio.pk}))
    assert resp.status_code == 200
    assert resp.context["allocation_charts"] == []


@pytest.mark.django_db
def test_refresh_quotes_dispatches_for_held_assets(auth_client, user):
    asset = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal("1"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    url = reverse("portfolio:refresh_quotes", kwargs={"pk": portfolio.pk})
    with patch("apps.portfolio.views.fetch_and_store_quote") as fetch:
        resp = auth_client.post(url)

    assert resp.status_code == 302
    fetch.assert_called_once_with(asset)


@pytest.mark.django_db
def test_refresh_quotes_requires_ownership(auth_client, other_user):
    foreign = Portfolio.objects.create(
        owner=other_user, name="Theirs", base_currency="USD"
    )
    url = reverse("portfolio:refresh_quotes", kwargs={"pk": foreign.pk})
    resp = auth_client.post(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_refresh_quotes_rejects_get(auth_client, user):
    portfolio = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    url = reverse("portfolio:refresh_quotes", kwargs={"pk": portfolio.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 405  # method not allowed
