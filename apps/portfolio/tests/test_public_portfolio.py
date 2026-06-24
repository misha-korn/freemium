"""Public portfolio sharing — opt-in, token-gated, money-free (Tier 3 #10)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.marketdata.models import PriceQuote
from apps.portfolio.models import Asset, Portfolio, Transaction


def _portfolio_with_holding(user, *, name="Main"):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name=name, base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    PriceQuote.objects.create(
        asset=asset, price=Decimal("150"), currency="USD",
        as_of=datetime.now(UTC), source="TEST",
    )
    return pf


# --- publish / unpublish --------------------------------------------------- #
@pytest.mark.django_db
def test_publish_sets_token_and_exposes_public_view(auth_client, user):
    pf = _portfolio_with_holding(user)
    publish = auth_client.post(
        reverse("portfolio:share", kwargs={"pk": pf.pk}), {"action": "publish"}
    )
    assert publish.status_code == 302
    pf.refresh_from_db()
    assert pf.is_public is True
    assert pf.share_token

    resp = auth_client.get(reverse("public_portfolio", kwargs={"token": pf.share_token}))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_private_portfolio_link_404s(client, user):
    pf = _portfolio_with_holding(user)
    pf.share_token = "sometoken123"  # token set but not public
    pf.save(update_fields=["share_token"])
    resp = client.get(reverse("public_portfolio", kwargs={"token": "sometoken123"}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_unpublish_makes_link_404(auth_client, user):
    pf = _portfolio_with_holding(user)
    auth_client.post(reverse("portfolio:share", kwargs={"pk": pf.pk}), {"action": "publish"})
    pf.refresh_from_db()
    token = pf.share_token

    auth_client.post(reverse("portfolio:share", kwargs={"pk": pf.pk}), {"action": "unpublish"})
    resp = auth_client.get(reverse("public_portfolio", kwargs={"token": token}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_unknown_token_404s(client):
    resp = client.get(reverse("public_portfolio", kwargs={"token": "nope-nope"}))
    assert resp.status_code == 404


# --- privacy --------------------------------------------------------------- #
@pytest.mark.django_db
def test_public_view_hides_money_and_owner(client, user):
    pf = _portfolio_with_holding(user)
    pf.is_public = True
    pf.share_token = "pubtoken123"
    pf.save(update_fields=["is_public", "share_token"])

    html = client.get(reverse("public_portfolio", kwargs={"token": "pubtoken123"})).content.decode()
    # Composition is shown (ticker + weight), but no absolute amounts or owner.
    assert "AAPL" in html
    assert user.username not in html
    assert user.email not in html
    assert "1500" not in html  # market value must not leak
    assert "1000" not in html  # invested must not leak


@pytest.mark.django_db
def test_public_view_is_accessible_anonymously(client, user):
    pf = _portfolio_with_holding(user)
    pf.is_public = True
    pf.share_token = "anontoken"
    pf.save(update_fields=["is_public", "share_token"])
    resp = client.get(reverse("public_portfolio", kwargs={"token": "anontoken"}))
    assert resp.status_code == 200  # no login required


# --- ownership ------------------------------------------------------------- #
@pytest.mark.django_db
def test_cannot_share_others_portfolio(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    assert auth_client.get(reverse("portfolio:share", kwargs={"pk": foreign.pk})).status_code == 404
    assert auth_client.post(
        reverse("portfolio:share", kwargs={"pk": foreign.pk}), {"action": "publish"}
    ).status_code == 404
    foreign.refresh_from_db()
    assert foreign.is_public is False


@pytest.mark.django_db
def test_detail_page_links_to_share(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    html = auth_client.get(reverse("portfolio:detail", kwargs={"pk": pf.pk})).content.decode()
    assert reverse("portfolio:share", kwargs={"pk": pf.pk}) in html
