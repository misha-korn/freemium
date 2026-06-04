"""Tests for portfolio allocation breakdowns (Stage 3).

``build_allocation`` is pure — it takes already-valued positions (the same
``ValuedPosition`` objects ``portfolio_valuation`` produces) and groups their
base-currency value across several diversification axes. So these tests use
lightweight ``SimpleNamespace`` assets and need no database.
"""
from decimal import Decimal
from types import SimpleNamespace

from apps.portfolio.allocation import build_allocation, chart_payload
from apps.portfolio.services import Position
from apps.portfolio.valuation import ValuedPosition


def _valued(
    ticker: str,
    *,
    asset_type: str = "STOCK",
    market: str = "US",
    currency: str = "USD",
    invested: str = "1000",
    market_value: str | None = None,
) -> ValuedPosition:
    """Build a ValuedPosition with just the fields allocation reads."""
    asset = SimpleNamespace(
        ticker=ticker, asset_type=asset_type, market=market, currency=currency
    )
    invested_dec = Decimal(invested)
    pos = Position(
        asset=asset,
        quantity=Decimal("1"),
        avg_cost=invested_dec,
        invested=invested_dec,
        currency=currency,
    )
    mv = Decimal(market_value) if market_value is not None else None
    return ValuedPosition(
        position=pos,
        price=mv,
        as_of=None,
        market_value=mv,
        unrealised_pnl=(mv - invested_dec) if mv is not None else None,
        simple_return=None,
    )


# --------------------------------------------------------------------------- #
# Basis selection
# --------------------------------------------------------------------------- #
def test_allocation_uses_invested_basis_when_not_fully_priced():
    # One priced, one unpriced -> we fall back to the always-known cost basis.
    valued = [
        _valued("AAPL", invested="1000", market_value="1500"),
        _valued("MSFT", invested="3000", market_value=None),
    ]
    alloc = build_allocation(valued, "USD")

    assert alloc["basis"] == "invested"
    assert alloc["available"] is True
    assert alloc["total"] == Decimal("4000")
    by_holding = {s.label: s for s in alloc["by_holding"]}
    # Weights are computed on invested capital: 1000 / 4000 and 3000 / 4000.
    assert by_holding["AAPL"].weight == Decimal("0.25")
    assert by_holding["MSFT"].weight == Decimal("0.75")
    # Sorted by value, descending.
    assert [s.label for s in alloc["by_holding"]] == ["MSFT", "AAPL"]


def test_allocation_uses_market_basis_when_fully_priced():
    valued = [
        _valued("AAPL", invested="1000", market_value="1500"),
        _valued("MSFT", invested="3000", market_value="1500"),
    ]
    alloc = build_allocation(valued, "USD")

    assert alloc["basis"] == "market"
    assert alloc["total"] == Decimal("3000")  # market values, not cost basis
    by_holding = {s.label: s for s in alloc["by_holding"]}
    assert by_holding["AAPL"].weight == Decimal("0.5")
    assert by_holding["MSFT"].weight == Decimal("0.5")


# --------------------------------------------------------------------------- #
# Grouping axes
# --------------------------------------------------------------------------- #
def test_allocation_groups_by_class_currency_and_market():
    valued = [
        _valued("AAPL", asset_type="STOCK", market="US", currency="USD", invested="1000"),
        _valued("VOO", asset_type="ETF", market="US", currency="USD", invested="1000"),
        _valued("SBER", asset_type="STOCK", market="MOEX", currency="USD", invested="2000"),
    ]
    alloc = build_allocation(valued, "USD")

    by_class = {s.label: s.value for s in alloc["by_class"]}
    assert by_class == {"Stock": Decimal("3000"), "ETF": Decimal("1000")}

    by_market = {s.label: s.value for s in alloc["by_market"]}
    assert by_market == {"US Markets": Decimal("2000"), "Moscow Exchange": Decimal("2000")}

    # Human-readable labels come from the model choices, not raw codes.
    assert "STOCK" not in by_class
    assert "MOEX" not in by_market


def test_allocation_weights_sum_to_one():
    valued = [
        _valued("AAPL", invested="1000"),
        _valued("MSFT", invested="2000"),
        _valued("VOO", invested="3000"),
    ]
    alloc = build_allocation(valued, "USD")
    total_weight = sum(s.weight for s in alloc["by_holding"])
    assert total_weight == Decimal("1")


# --------------------------------------------------------------------------- #
# FX / honesty
# --------------------------------------------------------------------------- #
def test_allocation_converts_to_base_currency_with_fx():
    valued = [
        _valued("AAPL", currency="USD", invested="1000"),
        _valued("SBER", currency="RUB", invested="9000"),
    ]
    rates = {"RUB": {"USD": "0.01"}}  # 9000 RUB -> 90 USD
    alloc = build_allocation(valued, "USD", rates=rates)

    assert alloc["missing_fx"] == []
    by_holding = {s.label: s.value for s in alloc["by_holding"]}
    assert by_holding["AAPL"] == Decimal("1000")
    assert by_holding["SBER"] == Decimal("90.00000000")


def test_allocation_excludes_unconvertible_currency_and_flags_it():
    valued = [
        _valued("AAPL", currency="USD", invested="1000"),
        _valued("SBER", currency="RUB", invested="9000"),  # no FX rate
    ]
    alloc = build_allocation(valued, "USD")  # no rates configured

    assert "RUB" in alloc["missing_fx"]
    labels = [s.label for s in alloc["by_holding"]]
    assert labels == ["AAPL"]  # RUB position excluded from base-currency view
    assert alloc["total"] == Decimal("1000")


def test_allocation_empty_is_unavailable():
    alloc = build_allocation([], "USD")
    assert alloc["available"] is False
    assert alloc["total"] is None
    assert alloc["by_holding"] == []
    assert alloc["by_class"] == []


# --------------------------------------------------------------------------- #
# Chart payload
# --------------------------------------------------------------------------- #
def test_chart_payload_shapes_labels_and_percentages():
    valued = [
        _valued("AAPL", invested="2500"),
        _valued("MSFT", invested="7500"),
    ]
    alloc = build_allocation(valued, "USD")
    payload = chart_payload(alloc["by_holding"])

    assert payload["labels"] == ["MSFT", "AAPL"]
    # Percentages are plain floats (chart-only; money stays Decimal elsewhere).
    assert payload["values"] == [75.0, 25.0]
    assert all(isinstance(v, float) for v in payload["values"])


def test_chart_payload_empty():
    payload = chart_payload([])
    assert payload == {"labels": [], "values": []}
