"""Tests for CSV trade import (Stage 5 — broker-import stand-in)."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.portfolio.imports import import_trades_csv
from apps.portfolio.models import Asset, Portfolio, Transaction

HEADER = "ticker,market,kind,quantity,price,fee,executed_at\n"


def _csv(*rows: str) -> bytes:
    return (HEADER + "".join(r + "\n" for r in rows)).encode("utf-8")


@pytest.fixture
def portfolio(user):
    Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    return Portfolio.objects.create(owner=user, name="P", base_currency="USD")


@pytest.mark.django_db
def test_import_creates_trade(portfolio):
    result = import_trades_csv(portfolio, _csv("AAPL,US,BUY,10,100,1,2024-01-02"))
    assert result["created"] == 1
    assert result["errors"] == []
    txn = Transaction.objects.get(portfolio=portfolio)
    assert txn.kind == "BUY"
    assert str(txn.quantity) == "10.00000000"
    assert txn.executed_at.year == 2024


@pytest.mark.django_db
def test_import_multiple_rows(portfolio):
    result = import_trades_csv(
        portfolio,
        _csv("AAPL,US,BUY,10,100,0,2024-01-02", "AAPL,US,SELL,5,150,0,2024-03-02"),
    )
    assert result["created"] == 2
    assert Transaction.objects.filter(portfolio=portfolio).count() == 2


@pytest.mark.django_db
def test_import_reports_unknown_asset(portfolio):
    result = import_trades_csv(portfolio, _csv("ZZZ,US,BUY,10,100,0,2024-01-02"))
    assert result["created"] == 0
    assert len(result["errors"]) == 1
    assert "ZZZ" in result["errors"][0]


@pytest.mark.django_db
def test_import_reports_bad_quantity(portfolio):
    result = import_trades_csv(portfolio, _csv("AAPL,US,BUY,0,100,0,2024-01-02"))
    assert result["created"] == 0
    assert len(result["errors"]) == 1


@pytest.mark.django_db
def test_import_reports_bad_kind(portfolio):
    result = import_trades_csv(portfolio, _csv("AAPL,US,HOLD,10,100,0,2024-01-02"))
    assert result["created"] == 0
    assert len(result["errors"]) == 1


@pytest.mark.django_db
def test_import_mixes_valid_and_invalid(portfolio):
    result = import_trades_csv(
        portfolio,
        _csv("AAPL,US,BUY,10,100,0,2024-01-02", "AAPL,US,BUY,bad,100,0,2024-01-02"),
    )
    assert result["created"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.django_db
def test_import_view_uploads_file(auth_client, portfolio):
    upload = SimpleUploadedFile(
        "trades.csv", _csv("AAPL,US,BUY,10,100,0,2024-01-02"), content_type="text/csv"
    )
    resp = auth_client.post(
        reverse("portfolio:import_trades", kwargs={"pk": portfolio.pk}),
        {"file": upload},
    )
    assert resp.status_code == 302
    assert Transaction.objects.filter(portfolio=portfolio).count() == 1


@pytest.mark.django_db
def test_import_view_requires_ownership(auth_client, other_user):
    Asset.objects.get_or_create(
        ticker="AAPL", market="US",
        defaults={"asset_type": "STOCK", "currency": "USD"},
    )
    foreign = Portfolio.objects.create(owner=other_user, name="Theirs", base_currency="USD")
    upload = SimpleUploadedFile("t.csv", _csv("AAPL,US,BUY,1,100,0,2024-01-02"))
    resp = auth_client.post(
        reverse("portfolio:import_trades", kwargs={"pk": foreign.pk}), {"file": upload}
    )
    assert resp.status_code == 404
