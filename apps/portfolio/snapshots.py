"""Portfolio value-over-time snapshots — Tier 1.

Records one mark-to-market ``PortfolioSnapshot`` per portfolio per day and reads
them back as a time series for an honest value-over-time chart.

Honesty rule (same as valuation): a snapshot is stored only when the portfolio is
**fully priced** and the base-currency total exists (every currency converts);
otherwise we skip the day rather than persist a misleading partial value. The
series therefore accumulates forward from the first fully-priced day — we never
back-date today's price onto past holdings.

Money is Decimal — never float.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

from .models import PortfolioSnapshot
from .valuation import portfolio_valuation

if TYPE_CHECKING:
    from .models import Portfolio

_MONEY = Decimal("0.01")


def take_snapshot(
    portfolio: Portfolio, *, valuation: dict | None = None
) -> PortfolioSnapshot | None:
    """Record today's mark-to-market value for ``portfolio``.

    Returns the stored snapshot, or ``None`` when the portfolio isn't fully
    priced / convertible today (nothing is stored — no fabricated value).

    Idempotent per day: a second call on the same date updates the existing row
    (``update_or_create`` on the ``(portfolio, as_of)`` unique constraint), so
    viewing a portfolio many times a day keeps a single, freshest snapshot.

    Pass a precomputed ``valuation`` to avoid recomputing it (e.g. the detail
    view already has one).
    """
    if valuation is None:
        valuation = portfolio_valuation(portfolio)

    totals = valuation["totals"]
    market_value = totals["market_value_base"]
    invested = totals["invested_base"]
    if market_value is None or invested is None:
        return None

    snapshot, _created = PortfolioSnapshot.objects.update_or_create(
        portfolio=portfolio,
        as_of=timezone.now().date(),
        defaults={
            "market_value": market_value.quantize(_MONEY),
            "invested": invested.quantize(_MONEY),
            "currency": valuation["base_currency"],
        },
    )
    return snapshot


def take_all_snapshots() -> int:
    """Take a snapshot for every portfolio; return how many were stored.

    Portfolios that aren't fully priced today are skipped (see ``take_snapshot``).
    """
    from .models import Portfolio

    stored = 0
    for portfolio in Portfolio.objects.all().iterator():
        if take_snapshot(portfolio) is not None:
            stored += 1
    return stored


def value_timeseries(portfolio: Portfolio) -> dict:
    """Stored mark-to-market value over time, oldest first, for the chart.

    Shape::

        {
          "base_currency": str,
          "available": bool,            # True when >= 1 snapshot exists
          "points": [{"date", "market_value", "invested"}],
        }
    """
    snapshots = portfolio.snapshots.all()  # model default ordering: as_of asc
    points = [
        {
            "date": snap.as_of.isoformat(),
            "market_value": str(snap.market_value),
            "invested": str(snap.invested),
        }
        for snap in snapshots
    ]
    return {
        "base_currency": portfolio.base_currency,
        "available": bool(points),
        "points": points,
    }
