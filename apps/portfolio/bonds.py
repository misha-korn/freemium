"""Bond maths — Tier 2 (#5): accrued coupon (НКД), next coupon, maturity.

Pure functions over a ``BondDetail``. Coupon dates are derived by stepping back
from the maturity date by the coupon period (a standard assumption when the
explicit schedule isn't known), so we need only face value, coupon rate,
frequency and maturity — all manually entered. Accrued interest uses simple
linear day-count accrual between the surrounding coupon dates.

Pricing from the MOEX bonds market is a separate follow-up; nothing here invents
a market price. Money is Decimal — never float.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta

if TYPE_CHECKING:
    from .models import BondDetail

_MONEY = Decimal("0.01")


def coupon_period_months(detail: BondDetail) -> int:
    """Months between coupons (e.g. 6 for semi-annual)."""
    return 12 // detail.coupon_frequency


def coupon_bounds(detail: BondDetail, as_of: date) -> tuple[date, date] | None:
    """Return ``(previous_coupon, next_coupon)`` around ``as_of``.

    Coupon dates are derived backward from maturity by the coupon period. Returns
    ``None`` once the bond has matured (``as_of`` on/after maturity) — there are
    no further coupons to accrue.
    """
    maturity = detail.maturity_date
    if as_of >= maturity:
        return None
    period = coupon_period_months(detail)
    nxt = maturity
    while True:
        earlier = nxt - relativedelta(months=period)
        if earlier <= as_of:
            return earlier, nxt
        nxt = earlier


def accrued_interest(detail: BondDetail, as_of: date) -> Decimal:
    """Accrued coupon income (НКД) **per unit** at ``as_of``, in asset currency.

    Linear accrual: coupon × (days since previous coupon / days in the period).
    Zero once matured.
    """
    bounds = coupon_bounds(detail, as_of)
    if bounds is None:
        return Decimal("0")
    previous, nxt = bounds
    period_days = (nxt - previous).days
    if period_days <= 0:
        return Decimal("0")
    elapsed = (as_of - previous).days
    elapsed = max(0, min(elapsed, period_days))
    accrued = detail.coupon_amount * Decimal(elapsed) / Decimal(period_days)
    return accrued.quantize(_MONEY)


def next_coupon(detail: BondDetail, as_of: date) -> dict | None:
    """The upcoming coupon as ``{"date", "amount"}`` per unit, or None if matured."""
    bounds = coupon_bounds(detail, as_of)
    if bounds is None:
        return None
    return {"date": bounds[1], "amount": detail.coupon_amount.quantize(_MONEY)}


def upcoming_coupons(detail: BondDetail, as_of: date, end: date) -> list[dict]:
    """Per-unit coupons due in ``(as_of, end]`` up to maturity.

    Each item is ``{"date", "amount"}``. Empty once matured. Used by the income
    forecast — fully deterministic from the coupon schedule, no external data.
    """
    bounds = coupon_bounds(detail, as_of)
    if bounds is None:
        return []
    period = coupon_period_months(detail)
    amount = detail.coupon_amount.quantize(_MONEY)
    coupons: list[dict] = []
    when = bounds[1]  # first coupon strictly after as_of
    while when <= end and when <= detail.maturity_date:
        coupons.append({"date": when, "amount": amount})
        when = when + relativedelta(months=period)
    return coupons


def days_to_maturity(detail: BondDetail, as_of: date) -> int:
    """Calendar days until maturity (negative if already matured)."""
    return (detail.maturity_date - as_of).days


def bond_summary(detail: BondDetail, as_of: date, *, quantity: Decimal | None = None) -> dict:
    """Reference figures for a bond holding (per unit, plus totals if quantity given).

    Shape::

        {
          "currency": str,
          "matured": bool,
          "days_to_maturity": int,
          "coupon_amount": Decimal,       # per unit, per period
          "accrued_interest": Decimal,    # per unit (НКД)
          "next_coupon": {"date", "amount"} | None,
          "accrued_total": Decimal | None,    # × quantity, when given
          "face_total": Decimal | None,       # face × quantity, when given
        }
    """
    accrued = accrued_interest(detail, as_of)
    matured = as_of >= detail.maturity_date
    summary = {
        "currency": detail.asset.currency,
        "matured": matured,
        "days_to_maturity": days_to_maturity(detail, as_of),
        "coupon_amount": detail.coupon_amount.quantize(_MONEY),
        "accrued_interest": accrued,
        "next_coupon": next_coupon(detail, as_of),
        "accrued_total": None,
        "face_total": None,
    }
    if quantity is not None:
        summary["accrued_total"] = (accrued * quantity).quantize(_MONEY)
        summary["face_total"] = (detail.face_value * quantity).quantize(_MONEY)
    return summary
