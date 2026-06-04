from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.marketdata.models import PriceQuote
from apps.marketdata.providers.base import Quote
from apps.marketdata.tasks import refresh_active_quotes, refresh_quote
from apps.portfolio.models import Asset, Portfolio, Transaction


def _quote(symbol: str = "SBER") -> Quote:
    return Quote(
        symbol=symbol,
        price=Decimal("250.5"),
        currency="RUB",
        as_of=datetime.now(UTC),
        source="MOEX",
    )


@pytest.mark.django_db
def test_refresh_quote_persists_and_returns_summary():
    asset = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    with patch(
        "apps.marketdata.services.get_provider"
    ) as get_provider:
        get_provider.return_value.get_quote.return_value = _quote()
        result = refresh_quote(asset.id)

    assert result == {
        "asset_id": asset.id,
        "price": "250.5",
        "currency": "RUB",
        "source": "MOEX",
    }
    assert PriceQuote.objects.filter(asset=asset).count() == 1


@pytest.mark.django_db
def test_refresh_quote_missing_asset_returns_none():
    assert refresh_quote(999_999) is None


@pytest.mark.django_db
def test_refresh_quote_no_quote_returns_none():
    asset = Asset.objects.create(
        ticker="NOPE", asset_type="STOCK", market="OTHER", currency="USD"
    )
    with patch("apps.marketdata.services.get_provider") as get_provider:
        get_provider.return_value.get_quote.return_value = None
        assert refresh_quote(asset.id) is None
    assert PriceQuote.objects.count() == 0


@pytest.mark.django_db
def test_refresh_active_quotes_dispatches_only_traded_assets(user):
    traded = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    # Untraded asset must be ignored.
    Asset.objects.create(
        ticker="LKOH", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="RU", base_currency="RUB")
    Transaction.objects.create(
        portfolio=portfolio, asset=traded, kind="BUY",
        quantity=Decimal("1"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    with patch("apps.marketdata.tasks.refresh_quote.delay") as delay:
        count = refresh_active_quotes()

    assert count == 1
    delay.assert_called_once_with(traded.id)
