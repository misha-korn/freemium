"""Portfolio value-over-time snapshots: store-when-priced + time series (Tier 1)."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.marketdata.models import PriceQuote
from apps.portfolio.models import Asset, Portfolio, PortfolioSnapshot, Transaction
from apps.portfolio.snapshots import (
    take_all_snapshots,
    take_snapshot,
    value_timeseries,
)


def _priced_portfolio(user, *, currency="USD", market="US", ticker="AAPL") -> Portfolio:
    asset = Asset.objects.create(
        ticker=ticker, asset_type="STOCK", market=market, currency=currency
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency=currency)
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    PriceQuote.objects.create(
        asset=asset, price=Decimal("150"), currency=currency,
        as_of=datetime.now(UTC), source="TEST",
    )
    return pf


@pytest.mark.django_db
def test_take_snapshot_stores_when_fully_priced(user):
    pf = _priced_portfolio(user)

    snap = take_snapshot(pf)

    assert snap is not None
    assert snap.market_value == Decimal("1500.00")  # 10 * 150
    assert snap.invested == Decimal("1000.00")  # 10 * 100
    assert snap.currency == "USD"
    assert PortfolioSnapshot.objects.filter(portfolio=pf).count() == 1


@pytest.mark.django_db
def test_take_snapshot_skips_when_unpriced(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )  # no PriceQuote -> unpriced

    assert take_snapshot(pf) is None
    assert PortfolioSnapshot.objects.count() == 0


@pytest.mark.django_db
def test_take_snapshot_skips_when_fx_missing(user):
    """A currency with no FX rate to base must not be snapshotted (no guess)."""
    asset = Asset.objects.create(
        ticker="SBER", asset_type="STOCK", market="MOEX", currency="RUB"
    )
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    PriceQuote.objects.create(
        asset=asset, price=Decimal("150"), currency="RUB",
        as_of=datetime.now(UTC), source="TEST",
    )

    # FX_RATES is empty by default -> RUB can't convert to USD base.
    assert take_snapshot(pf) is None
    assert PortfolioSnapshot.objects.count() == 0


@pytest.mark.django_db
def test_take_snapshot_is_idempotent_per_day(user):
    pf = _priced_portfolio(user)

    first = take_snapshot(pf)
    second = take_snapshot(pf)

    assert first.pk == second.pk  # same row updated, not duplicated
    assert PortfolioSnapshot.objects.filter(portfolio=pf).count() == 1


@pytest.mark.django_db
def test_value_timeseries_oldest_first(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    PortfolioSnapshot.objects.create(
        portfolio=pf, as_of=date(2024, 2, 1), market_value=Decimal("1100"),
        invested=Decimal("1000"), currency="USD",
    )
    PortfolioSnapshot.objects.create(
        portfolio=pf, as_of=date(2024, 1, 1), market_value=Decimal("1000"),
        invested=Decimal("1000"), currency="USD",
    )

    series = value_timeseries(pf)

    assert series["available"] is True
    assert [p["date"] for p in series["points"]] == ["2024-01-01", "2024-02-01"]
    assert series["points"][1]["market_value"] == "1100.00"


@pytest.mark.django_db
def test_value_timeseries_empty_when_no_snapshots(user):
    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    series = value_timeseries(pf)
    assert series["available"] is False
    assert series["points"] == []


@pytest.mark.django_db
def test_take_all_snapshots_counts_only_priced(user, other_user):
    _priced_portfolio(user, ticker="AAPL")
    # An unpriced portfolio for another user — must be skipped.
    unpriced_asset = Asset.objects.create(
        ticker="MSFT", asset_type="STOCK", market="US", currency="USD"
    )
    unpriced = Portfolio.objects.create(owner=other_user, name="U", base_currency="USD")
    Transaction.objects.create(
        portfolio=unpriced, asset=unpriced_asset, kind="BUY", quantity=Decimal("1"),
        price=Decimal("10"), fee=Decimal("0"),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    assert take_all_snapshots() == 1


@pytest.mark.django_db
def test_snapshot_task_stores(user):
    from apps.portfolio.tasks import snapshot_portfolios

    _priced_portfolio(user)
    stored = snapshot_portfolios()  # eager in tests
    assert stored == 1


@pytest.mark.django_db
def test_detail_view_records_snapshot_when_priced(auth_client, user):
    from django.urls import reverse

    pf = _priced_portfolio(user)
    auth_client.get(reverse("portfolio:detail", kwargs={"pk": pf.pk}))
    assert PortfolioSnapshot.objects.filter(portfolio=pf).count() == 1


@pytest.mark.django_db
def test_detail_view_renders_value_chart_with_history(auth_client, user):
    from django.urls import reverse

    pf = Portfolio.objects.create(owner=user, name="P", base_currency="USD")
    for d, mv in [(date(2024, 1, 1), "1000"), (date(2024, 1, 2), "1100")]:
        PortfolioSnapshot.objects.create(
            portfolio=pf, as_of=d, market_value=Decimal(mv),
            invested=Decimal("1000"), currency="USD",
        )

    resp = auth_client.get(reverse("portfolio:detail", kwargs={"pk": pf.pk}))
    assert resp.status_code == 200
    assert len(resp.context["value_chart"]["points"]) >= 2
    assert b'id="portfolio-value-chart"' in resp.content
