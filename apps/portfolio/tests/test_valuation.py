from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.marketdata.models import PriceQuote
from apps.portfolio.models import Asset, Portfolio, Transaction
from apps.portfolio.services import Position
from apps.portfolio.valuation import (
    invested_timeseries,
    portfolio_valuation,
    value_positions,
)


# --------------------------------------------------------------------------- #
# value_positions — pure (no DB)
# --------------------------------------------------------------------------- #
def _position(asset_id: int, qty: str, invested: str, currency: str = "USD") -> Position:
    asset = SimpleNamespace(id=asset_id, ticker=f"A{asset_id}", currency=currency)
    quantity = Decimal(qty)
    invested_dec = Decimal(invested)
    return Position(
        asset=asset,
        quantity=quantity,
        avg_cost=(invested_dec / quantity),
        invested=invested_dec,
        currency=currency,
    )


def _price(price: str, currency: str = "USD") -> SimpleNamespace:
    return SimpleNamespace(
        price=Decimal(price), currency=currency, as_of=datetime.now(UTC)
    )


def test_value_positions_prices_and_returns():
    pos = _position(1, "10", "1000")
    [valued] = value_positions([pos], {1: _price("110")})

    assert valued.priced is True
    assert valued.market_value == Decimal("1100")
    assert valued.unrealised_pnl == Decimal("100")
    assert valued.simple_return == Decimal("0.1")
    assert valued.return_pct == Decimal("10.00")


def test_value_positions_without_quote_is_unpriced():
    pos = _position(1, "10", "1000")
    [valued] = value_positions([pos], {})  # no price for asset 1
    assert valued.priced is False
    assert valued.market_value is None
    assert valued.return_pct is None


def test_value_positions_currency_mismatch_is_unpriced():
    pos = _position(1, "10", "1000", currency="USD")
    [valued] = value_positions([pos], {1: _price("110", currency="RUB")})
    assert valued.priced is False


# --------------------------------------------------------------------------- #
# portfolio_valuation — integration
# --------------------------------------------------------------------------- #
def _quote(asset: Asset, price: str, currency: str) -> PriceQuote:
    return PriceQuote.objects.create(
        asset=asset,
        price=Decimal(price),
        currency=currency,
        as_of=datetime.now(UTC),
        source="TEST",
    )


def _buy(portfolio: Portfolio, asset: Asset, qty: str, price: str, day: int = 1) -> None:
    Transaction.objects.create(
        portfolio=portfolio,
        asset=asset,
        kind="BUY",
        quantity=Decimal(qty),
        price=Decimal(price),
        fee=Decimal("0"),
        executed_at=datetime(2024, 1, day, tzinfo=UTC),
    )


@pytest.mark.django_db
def test_portfolio_valuation_single_currency_priced(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="US", base_currency="USD")
    _buy(portfolio, asset, "10", "100")  # invested 1000
    _quote(asset, "150", "USD")  # market 1500

    result = portfolio_valuation(portfolio)
    totals = result["totals"]

    assert result["fully_priced"] is True
    assert result["missing_prices"] == []
    assert result["missing_fx"] == []
    assert totals["invested_base"] == Decimal("1000")
    assert totals["market_value_base"] == Decimal("1500")
    assert totals["unrealised_pnl_base"] == Decimal("500")
    assert totals["simple_return"] == Decimal("0.5")
    assert totals["xirr"] is not None and totals["xirr"] > 0


@pytest.mark.django_db
def test_portfolio_valuation_unpriced_position(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="US", base_currency="USD")
    _buy(portfolio, asset, "10", "100")  # no quote stored

    result = portfolio_valuation(portfolio)
    totals = result["totals"]

    assert result["fully_priced"] is False
    assert result["missing_prices"] == ["AAPL"]
    # Cost basis still aggregates; market value cannot (no price), so it's None.
    assert totals["invested_base"] == Decimal("1000")
    assert totals["market_value_base"] is None
    assert totals["xirr"] is None


@pytest.mark.django_db
def test_portfolio_valuation_multicurrency_without_fx(user):
    ru = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Mixed", base_currency="USD")
    _buy(portfolio, ru, "10", "100")
    _quote(ru, "120", "RUB")

    result = portfolio_valuation(portfolio)  # no FX rates configured

    assert "RUB" in result["missing_fx"]
    assert result["totals"]["invested_base"] is None
    assert result["totals"]["market_value_base"] is None
    # Per-currency figures stay exact even without FX.
    assert result["by_currency"]["RUB"]["market_value"] == Decimal("1200")


@pytest.mark.django_db
def test_portfolio_valuation_multicurrency_with_fx(user):
    ru = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Mixed", base_currency="USD")
    _buy(portfolio, ru, "10", "100")  # invested 1000 RUB
    _quote(ru, "120", "RUB")  # market 1200 RUB

    rates = {"RUB": {"USD": "0.01"}}
    result = portfolio_valuation(portfolio, rates=rates)
    totals = result["totals"]

    assert result["missing_fx"] == []
    assert totals["invested_base"] == Decimal("10.00000000")
    assert totals["market_value_base"] == Decimal("12.00000000")


# --------------------------------------------------------------------------- #
# invested_timeseries
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_invested_timeseries_accumulates(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    portfolio = Portfolio.objects.create(owner=user, name="US", base_currency="USD")
    _buy(portfolio, asset, "10", "100", day=1)  # +1000 -> 1000
    _buy(portfolio, asset, "5", "100", day=2)   # +500  -> 1500
    Transaction.objects.create(
        portfolio=portfolio, asset=asset, kind="SELL",
        quantity=Decimal("5"), price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 3, tzinfo=UTC),
    )  # -500 -> 1000

    series = invested_timeseries(portfolio)
    assert series["available"] is True
    assert [p["invested"] for p in series["points"]] == ["1000.00", "1500.00", "1000.00"]


@pytest.mark.django_db
def test_invested_timeseries_unavailable_without_fx(user):
    ru = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    portfolio = Portfolio.objects.create(owner=user, name="Mixed", base_currency="USD")
    _buy(portfolio, ru, "10", "100")

    series = invested_timeseries(portfolio)  # RUB -> USD rate missing
    assert series["available"] is False
    assert series["points"] == []
