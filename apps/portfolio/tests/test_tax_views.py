"""Tax report + export views: Pro gating and content (Stage 5)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.billing import subscriptions
from apps.portfolio.models import Asset, Portfolio, Transaction


def _portfolio_with_realized_gain(user) -> Portfolio:
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"), executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="SELL", quantity=Decimal("10"),
        price=Decimal("150"), fee=Decimal("0"), executed_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    return pf


@pytest.mark.django_db
def test_tax_report_blocked_for_free(auth_client, user):
    pf = _portfolio_with_realized_gain(user)
    resp = auth_client.get(reverse("portfolio:tax_report", kwargs={"pk": pf.pk}))
    assert resp.status_code == 302
    assert reverse("billing:pricing") in resp.url


@pytest.mark.django_db
def test_tax_report_renders_for_pro(auth_client, user):
    pf = _portfolio_with_realized_gain(user)
    subscriptions.activate_pro(user, provider="dev")
    resp = auth_client.get(reverse("portfolio:tax_report", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert resp.context["summary"]["USD"]["gain"] == Decimal("500")
    assert resp.context["year"] == 2024


@pytest.mark.django_db
def test_export_blocked_for_free(auth_client, user):
    pf = _portfolio_with_realized_gain(user)
    resp = auth_client.get(
        reverse("portfolio:export_transactions_csv", kwargs={"pk": pf.pk})
    )
    assert resp.status_code == 302
    assert reverse("billing:pricing") in resp.url


@pytest.mark.django_db
def test_export_tax_csv_for_pro(auth_client, user):
    pf = _portfolio_with_realized_gain(user)
    subscriptions.activate_pro(user, provider="dev")
    resp = auth_client.get(reverse("portfolio:export_tax_csv", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert "attachment" in resp["Content-Disposition"]
    body = resp.content.decode("utf-8-sig")
    assert "AAPL" in body
    assert "Gain" in body


@pytest.mark.django_db
def test_export_tax_xlsx_for_pro(auth_client, user):
    pf = _portfolio_with_realized_gain(user)
    subscriptions.activate_pro(user, provider="dev")
    resp = auth_client.get(reverse("portfolio:export_tax_xlsx", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
    assert resp.content[:2] == b"PK"  # .xlsx is a zip archive


@pytest.mark.django_db
def test_export_transactions_csv_for_pro(auth_client, user):
    pf = _portfolio_with_realized_gain(user)
    subscriptions.activate_pro(user, provider="dev")
    resp = auth_client.get(
        reverse("portfolio:export_transactions_csv", kwargs={"pk": pf.pk})
    )
    assert resp.status_code == 200
    body = resp.content.decode("utf-8-sig")
    assert "AAPL" in body
    assert "Date" in body
