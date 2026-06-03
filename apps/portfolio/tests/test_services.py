from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.portfolio.models import Asset, Portfolio, Transaction
from apps.portfolio.services import compute_positions, portfolio_summary


@pytest.mark.django_db
def test_compute_positions_average_cost(user):
    asset = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")

    def make(kind: str, qty: str, price: str, day: int) -> None:
        Transaction.objects.create(
            portfolio=portfolio,
            asset=asset,
            kind=kind,
            quantity=Decimal(qty),
            price=Decimal(price),
            fee=Decimal("0"),
            executed_at=datetime(2024, 1, day, tzinfo=UTC),
        )

    make("BUY", "10", "100", 1)   # basis 1000
    make("BUY", "10", "200", 2)   # basis 3000, qty 20 -> avg 150
    make("SELL", "5", "250", 3)   # qty 15, basis 3000 - 150*5 = 2250

    positions = compute_positions(portfolio)
    assert len(positions) == 1
    pos = positions[0]
    assert pos.quantity == Decimal("15")
    assert pos.invested == Decimal("2250")
    assert pos.avg_cost == Decimal("150.00000000")

    summary = portfolio_summary(portfolio)
    assert summary["positions_count"] == 1
    assert summary["invested_by_currency"]["RUB"] == Decimal("2250")


@pytest.mark.django_db
def test_sell_all_closes_position(user):
    asset = Asset.objects.create(
        ticker="GAZP", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="BUY",
        quantity=Decimal("5"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="SELL",
        quantity=Decimal("5"), price=Decimal("120"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert compute_positions(portfolio) == []
