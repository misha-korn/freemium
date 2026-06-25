"""Stock dividend estimate — Tier 3 (#9, estimate half).

Projects upcoming stock dividends from the imported ``AssetDividend`` history:
infer the pay cadence from past ex-dates, then step forward using the **latest**
per-share amount × shares held. These are clearly-labelled **estimates** (the
forecast UI marks them as such) — never presented as scheduled facts. We only
estimate when there are at least two real dividends to infer a cadence from; one
data point isn't enough, so we don't guess.

Money is Decimal — never float.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

_MONEY = Decimal("0.01")
# Standard payout cadences in months: monthly, quarterly, semi-annual, annual.
_STANDARD_PERIODS = (1, 3, 6, 12)
_DAYS_PER_MONTH = 30.44
_MAX_PROJECTED = 24  # safety bound on the projection loop


def infer_period_months(ex_dates: list[date]) -> int | None:
    """Infer the payout period (months) from sorted ex-dates, or None if <2."""
    if len(ex_dates) < 2:
        return None
    gaps = sorted((b - a).days for a, b in zip(ex_dates, ex_dates[1:], strict=False))
    median_gap = gaps[len(gaps) // 2]
    if median_gap <= 0:
        return None
    months = median_gap / _DAYS_PER_MONTH
    return min(_STANDARD_PERIODS, key=lambda p: abs(p - months))


def estimate_upcoming(
    records: list, quantity: Decimal, as_of: date, end: date
) -> list[dict]:
    """Estimated dividends in ``(as_of, end]`` for one asset.

    ``records`` are dividend rows (ascending ``ex_date``, with ``amount`` per
    share and ``currency``). Each result is
    ``{"date", "per_share", "amount", "currency"}`` where ``amount`` is
    ``per_share × quantity``. Empty when a cadence can't be inferred.
    """
    if len(records) < 2 or quantity <= 0:
        return []
    period = infer_period_months([r.ex_date for r in records])
    if period is None:
        return []

    latest = records[-1]
    out: list[dict] = []
    when = latest.ex_date
    for _ in range(_MAX_PROJECTED):
        when = when + relativedelta(months=period)
        if when > end:
            break
        if when > as_of:
            amount = (latest.amount * quantity).quantize(_MONEY)
            if amount > 0:
                out.append(
                    {
                        "date": when,
                        "per_share": latest.amount,
                        "amount": amount,
                        "currency": latest.currency,
                    }
                )
    return out


def trailing_annual_per_share(records: list, as_of: date) -> Decimal:
    """Sum of per-share dividends actually paid in the trailing 12 months."""
    start = as_of - relativedelta(months=12)
    return sum(
        (r.amount for r in records if start < r.ex_date <= as_of), Decimal("0")
    )
