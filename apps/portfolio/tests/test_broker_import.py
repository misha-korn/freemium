"""Broker report (.xlsx) import — tolerant table detection + auto-create (Tier 2)."""
import io
from datetime import datetime
from decimal import Decimal

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.portfolio.broker_import import import_broker_xlsx
from apps.portfolio.models import Asset, Portfolio, Transaction


def _xlsx(rows: list[tuple]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# A Tinkoff-style RU report: title/preamble rows, a trades header, two trades,
# a blank separator and a totals row that must be ignored.
_TINKOFF_ROWS = [
    ("Отчёт брокера", None, None, None, None, None, None),
    ("за период 01.01.2024 — 31.01.2024", None, None, None, None, None, None),
    (None, None, None, None, None, None, None),
    ("Дата заключения", "Вид сделки", "Тикер", "Цена за единицу",
     "Количество", "Валюта", "Комиссия брокера"),
    ("15.01.2024", "Покупка", "SBER", "250.5", "10", "RUB", "1.50"),
    ("16.01.2024", "Продажа", "SBER", "260", "4", "RUB", "0.80"),
    (None, None, None, None, None, None, None),
    ("Итого:", None, None, None, "6", None, "2.30"),
]


@pytest.mark.django_db
def test_imports_tinkoff_style_report_and_autocreates_asset(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")

    result = import_broker_xlsx(pf, _xlsx(_TINKOFF_ROWS))

    assert result["created"] == 2
    assert result["created_assets"] == ["SBER"]  # created once, reused on row 2
    assert result["errors"] == []

    sber = Asset.objects.get(ticker="SBER")
    assert sber.market == "MOEX"  # RUB -> MOEX inference
    assert sber.currency == "RUB"

    buy = Transaction.objects.get(portfolio=pf, kind="BUY")
    assert buy.quantity == Decimal("10")
    assert buy.price == Decimal("250.5")
    assert buy.fee == Decimal("1.50")
    assert buy.executed_at.date().isoformat() == "2024-01-15"
    assert Transaction.objects.filter(portfolio=pf, kind="SELL").count() == 1


@pytest.mark.django_db
def test_totals_and_blank_rows_are_skipped(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    result = import_broker_xlsx(pf, _xlsx(_TINKOFF_ROWS))
    # Only the two real trades — the "Итого" row carries no ticker/kind.
    assert Transaction.objects.filter(portfolio=pf).count() == 2
    assert result["created"] == 2


@pytest.mark.django_db
def test_matches_existing_asset_with_english_headers(user):
    Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    rows = [
        ("Date", "Operation", "Symbol", "Price", "Quantity", "Currency", "Fee"),
        ("2024-01-15", "Buy", "AAPL", "150.25", "10", "USD", "1"),
    ]

    result = import_broker_xlsx(pf, _xlsx(rows))

    assert result["created"] == 1
    assert result["created_assets"] == []  # AAPL already existed
    assert Asset.objects.filter(ticker="AAPL").count() == 1


@pytest.mark.django_db
def test_handles_datetime_cells(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    rows = [
        ("Дата", "Операция", "Тикер", "Цена", "Количество"),
        # Excel cells are timezone-naive; the parser makes them aware.
        (datetime(2024, 3, 1, 10, 30), "Покупка", "GAZP", 180.0, 5),
    ]

    result = import_broker_xlsx(pf, _xlsx(rows))

    assert result["created"] == 1
    txn = Transaction.objects.get(portfolio=pf)
    assert txn.price == Decimal("180.0")
    assert txn.quantity == Decimal("5")
    assert txn.executed_at.date().isoformat() == "2024-03-01"


@pytest.mark.django_db
def test_bad_row_is_reported_others_still_import(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    rows = [
        ("Дата", "Вид", "Тикер", "Цена", "Количество"),
        ("15.01.2024", "Покупка", "SBER", "250", "10"),
        ("16.01.2024", "Покупка", "SBER", "abc", "5"),  # bad price
    ]

    result = import_broker_xlsx(pf, _xlsx(rows))

    assert result["created"] == 1
    assert len(result["errors"]) == 1
    assert "price" in result["errors"][0]


@pytest.mark.django_db
def test_no_trades_table_reports_error(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    rows = [
        ("Отчёт брокера", None),
        ("Какой-то текст", "и числа"),
    ]

    result = import_broker_xlsx(pf, _xlsx(rows))

    assert result["created"] == 0
    assert result["errors"]
    assert "trades table" in result["errors"][0]


@pytest.mark.django_db
def test_unreadable_file_is_handled(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    result = import_broker_xlsx(pf, b"this is not an xlsx")
    assert result["created"] == 0
    assert result["errors"]


# --- view integration ------------------------------------------------------ #
@pytest.mark.django_db
def test_import_view_accepts_xlsx_upload(auth_client, user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="RUB")
    upload = SimpleUploadedFile(
        "report.xlsx",
        _xlsx(_TINKOFF_ROWS),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    resp = auth_client.post(
        reverse("portfolio:import_trades", kwargs={"pk": pf.pk}), {"file": upload}
    )

    assert resp.status_code == 302
    assert Transaction.objects.filter(portfolio=pf).count() == 2
    assert Asset.objects.filter(ticker="SBER").exists()


@pytest.mark.django_db
def test_import_view_still_accepts_csv(auth_client, user):
    Asset.objects.create(ticker="AAPL", asset_type="STOCK", market="US", currency="USD")
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    csv = b"ticker,market,kind,quantity,price,fee,executed_at\nAAPL,US,BUY,10,150,1,2024-01-15\n"
    upload = SimpleUploadedFile("trades.csv", csv, content_type="text/csv")

    resp = auth_client.post(
        reverse("portfolio:import_trades", kwargs={"pk": pf.pk}), {"file": upload}
    )

    assert resp.status_code == 302
    assert Transaction.objects.filter(portfolio=pf, kind="BUY").count() == 1
