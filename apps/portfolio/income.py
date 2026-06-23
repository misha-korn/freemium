"""Dividend & coupon income — Tier 1.

Pure read helpers over a portfolio's ``DividendPayment`` rows: history, a
per-currency summary, a month-by-month calendar, and yield-on-cost when the
cost basis in the same currency is known.

Honesty rules match the rest of the app: money is Decimal, figures stay
per-currency and are never mixed across currencies without an FX rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import DividendPayment, Portfolio


def dividend_history(
    portfolio: Portfolio, *, year: int | None = None
) -> list[DividendPayment]:
    """Return a portfolio's dividend/coupon payments, optionally for one year.

    Newest payment first (matches the model's default ordering).
    """
    qs = portfolio.dividends.select_related("asset").order_by("-paid_on", "-id")
    if year is not None:
        qs = qs.filter(paid_on__year=year)
    return list(qs)


def dividend_summary(payments: list[DividendPayment]) -> dict[str, dict[str, Decimal]]:
    """Aggregate payments into per-currency totals: gross, tax, net, count."""
    summary: dict[str, dict] = {}
    for payment in payments:
        bucket = summary.setdefault(
            payment.currency,
            {
                "gross": Decimal("0"),
                "tax": Decimal("0"),
                "net": Decimal("0"),
                "count": 0,
            },
        )
        bucket["gross"] += payment.amount
        bucket["tax"] += payment.tax_withheld
        bucket["net"] += payment.net_amount
        bucket["count"] += 1
    return summary


def dividend_years(portfolio: Portfolio) -> list[int]:
    """Distinct years in which this portfolio received income (newest first)."""
    return sorted(
        {p.paid_on.year for p in portfolio.dividends.all()}, reverse=True
    )


@dataclass(frozen=True)
class MonthGroup:
    """All payments received in one calendar month, with per-currency net total."""

    year: int
    month: int
    payments: list[DividendPayment]
    net_by_currency: dict[str, Decimal]


def dividend_calendar(payments: list[DividendPayment]) -> list[MonthGroup]:
    """Group payments by (year, month), newest month first.

    Each group carries its per-currency net income so a month shows what was
    actually received — never a cross-currency sum.
    """
    groups: dict[tuple[int, int], list[DividendPayment]] = {}
    for payment in payments:
        key = (payment.paid_on.year, payment.paid_on.month)
        groups.setdefault(key, []).append(payment)

    result: list[MonthGroup] = []
    for (year, month), items in sorted(groups.items(), reverse=True):
        net: dict[str, Decimal] = {}
        for payment in items:
            net[payment.currency] = (
                net.get(payment.currency, Decimal("0")) + payment.net_amount
            )
        result.append(
            MonthGroup(year=year, month=month, payments=items, net_by_currency=net)
        )
    return result


def yield_on_cost(
    summary: dict[str, dict[str, Decimal]],
    invested_by_currency: dict[str, Decimal],
) -> dict[str, Decimal | None]:
    """Net income ÷ cost basis per currency (a fraction, e.g. 0.07 == 7%).

    Returns ``None`` for a currency with no current cost basis (e.g. the
    position was fully sold) — we never divide by zero or fabricate a yield.
    """
    out: dict[str, Decimal | None] = {}
    for currency, bucket in summary.items():
        invested = invested_by_currency.get(currency)
        if invested and invested > 0:
            out[currency] = bucket["net"] / invested
        else:
            out[currency] = None
    return out
