"""Dividend views: ownership scoping, CRUD flow and rendering (Tier 1)."""
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.portfolio.models import Asset, DividendPayment, Portfolio


def _asset(ticker="AAPL", currency="USD", market="US") -> Asset:
    return Asset.objects.create(
        ticker=ticker, asset_type="STOCK", market=market, currency=currency
    )


@pytest.mark.django_db
def test_dividends_page_requires_login(client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    resp = client.get(reverse("portfolio:dividends", kwargs={"pk": pf.pk}))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url


@pytest.mark.django_db
def test_owner_cannot_see_others_dividends(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:dividends", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_empty_state_when_no_dividends(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:dividends", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert resp.context["summary"] == {}
    assert b"No dividends recorded yet" in resp.content


@pytest.mark.django_db
def test_add_dividend_flow(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    resp = auth_client.post(
        reverse("portfolio:dividend_create", kwargs={"pk": pf.pk}),
        {
            "asset": asset.pk,
            "kind": "DIVIDEND",
            "amount": "100",
            "tax_withheld": "13",
            "currency": "USD",
            "paid_on": "2024-03-15",
            "note": "Q1",
        },
    )
    assert resp.status_code == 302
    payment = DividendPayment.objects.get(portfolio=pf, asset=asset)
    assert payment.amount == Decimal("100")
    assert payment.net_amount == Decimal("87")


@pytest.mark.django_db
def test_blank_tax_is_treated_as_zero(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    resp = auth_client.post(
        reverse("portfolio:dividend_create", kwargs={"pk": pf.pk}),
        {
            "asset": asset.pk,
            "kind": "DIVIDEND",
            "amount": "50",
            "tax_withheld": "",
            "currency": "USD",
            "paid_on": "2024-03-15",
            "note": "",
        },
    )
    assert resp.status_code == 302
    assert DividendPayment.objects.get(portfolio=pf).tax_withheld == Decimal("0")


@pytest.mark.django_db
def test_reject_tax_greater_than_amount(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    resp = auth_client.post(
        reverse("portfolio:dividend_create", kwargs={"pk": pf.pk}),
        {
            "asset": asset.pk,
            "kind": "DIVIDEND",
            "amount": "100",
            "tax_withheld": "150",
            "currency": "USD",
            "paid_on": "2024-03-15",
            "note": "",
        },
    )
    assert resp.status_code == 200  # re-rendered with error
    assert DividendPayment.objects.count() == 0


@pytest.mark.django_db
def test_reject_zero_amount(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    resp = auth_client.post(
        reverse("portfolio:dividend_create", kwargs={"pk": pf.pk}),
        {
            "asset": asset.pk,
            "kind": "DIVIDEND",
            "amount": "0",
            "tax_withheld": "0",
            "currency": "USD",
            "paid_on": "2024-03-15",
            "note": "",
        },
    )
    assert resp.status_code == 200
    assert DividendPayment.objects.count() == 0


@pytest.mark.django_db
def test_cannot_add_dividend_to_others_portfolio(auth_client, other_user):
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:dividend_create", kwargs={"pk": foreign.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_list_renders_summary_and_calendar(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    DividendPayment.objects.create(
        portfolio=pf, asset=asset, kind="DIVIDEND", amount=Decimal("100"),
        tax_withheld=Decimal("13"), currency="USD", paid_on=date(2024, 3, 15),
    )
    resp = auth_client.get(reverse("portfolio:dividends", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert resp.context["summary"]["USD"]["net"] == Decimal("87")
    assert resp.context["year"] == 2024
    assert len(resp.context["calendar"]) == 1


@pytest.mark.django_db
def test_edit_and_delete_dividend(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    asset = _asset()
    payment = DividendPayment.objects.create(
        portfolio=pf, asset=asset, kind="DIVIDEND", amount=Decimal("100"),
        tax_withheld=Decimal("0"), currency="USD", paid_on=date(2024, 3, 15),
    )

    edit = auth_client.post(
        reverse("portfolio:dividend_update", kwargs={"pk": payment.pk}),
        {
            "asset": asset.pk, "kind": "DIVIDEND", "amount": "120",
            "tax_withheld": "0", "currency": "USD", "paid_on": "2024-03-15", "note": "",
        },
    )
    assert edit.status_code == 302
    payment.refresh_from_db()
    assert payment.amount == Decimal("120")

    delete = auth_client.post(
        reverse("portfolio:dividend_delete", kwargs={"pk": payment.pk})
    )
    assert delete.status_code == 302
    assert not DividendPayment.objects.filter(pk=payment.pk).exists()


@pytest.mark.django_db
def test_cannot_edit_others_dividend(auth_client, other_user):
    foreign_pf = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    asset = _asset()
    payment = DividendPayment.objects.create(
        portfolio=foreign_pf, asset=asset, kind="DIVIDEND", amount=Decimal("100"),
        tax_withheld=Decimal("0"), currency="USD", paid_on=date(2024, 3, 15),
    )
    resp = auth_client.get(reverse("portfolio:dividend_update", kwargs={"pk": payment.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_detail_page_links_to_dividends(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert reverse("portfolio:dividends", kwargs={"pk": pf.pk}).encode() in resp.content


@pytest.mark.django_db
def test_dividends_page_translates_to_russian(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    auth_client.post(reverse("set_language"), {"language": "ru", "next": "/"})
    html = auth_client.get(
        reverse("portfolio:dividends", kwargs={"pk": pf.pk})
    ).content.decode()
    assert "Дивиденды и купоны" in html
