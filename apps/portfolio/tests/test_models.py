from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.portfolio.models import Asset, Portfolio, Transaction


@pytest.mark.django_db
def test_transaction_gross_and_net_value(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Main", base_currency="USD")
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset=asset,
        kind="BUY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        fee=Decimal("5"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert txn.gross_value == Decimal("1000")
    assert txn.net_value == Decimal("1005")  # BUY adds fee

    txn.kind = "SELL"
    assert txn.net_value == Decimal("995")  # SELL subtracts fee
