"""Forward income forecast — Tier 3 (#9, honest slice).

Projects **expected future income** from instruments whose schedule is known
deterministically — currently **bond coupons** (from ``BondDetail``). Stock
dividends are intentionally NOT forecast here: that needs a forward-dividend data
source, and guessing from history would fabricate numbers (the project's
cardinal sin). Figures stay per-currency and are never summed across currencies.

Money is Decimal — never float.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from . import bonds
from .models import BondDetail
from .services import compute_positions

if TYPE_CHECKING:
    from datetime import date

    from .models import Portfolio

_MONEY = Decimal("0.01")
DEFAULT_HORIZON_MONTHS = 12


def income_forecast(
    portfolio: Portfolio, *, months: int = DEFAULT_HORIZON_MONTHS, as_of: date | None = None
) -> dict:
    """Expected bond-coupon income over the next ``months``.

    Shape::

        {
          "horizon_months": int,
          "has_bond_details": bool,        # any held bond carries details
          "currency_totals": {cur: Decimal},
          "months": [ {year, month, events: [{asset, date, amount, currency}],
                       totals: {cur: Decimal}} ],   # chronological
        }
    """
    today = as_of or timezone.now().date()
    end = today + relativedelta(months=months)

    bond_positions = [
        pos for pos in compute_positions(portfolio) if pos.asset.asset_type == "BOND"
    ]
    details = {
        bond.asset_id: bond
        for bond in BondDetail.objects.filter(
            asset_id__in=[pos.asset.id for pos in bond_positions]
        )
    }

    groups: dict[tuple[int, int], dict] = {}
    currency_totals: dict[str, Decimal] = {}
    has_bond_details = False

    for pos in bond_positions:
        detail = details.get(pos.asset.id)
        if detail is None:
            continue
        has_bond_details = True
        currency = pos.asset.currency
        for coupon in bonds.upcoming_coupons(detail, today, end):
            amount = (coupon["amount"] * pos.quantity).quantize(_MONEY)
            key = (coupon["date"].year, coupon["date"].month)
            bucket = groups.setdefault(key, {"events": [], "totals": {}})
            bucket["events"].append(
                {
                    "asset": pos.asset,
                    "date": coupon["date"],
                    "amount": amount,
                    "currency": currency,
                }
            )
            bucket["totals"][currency] = bucket["totals"].get(currency, Decimal("0")) + amount
            currency_totals[currency] = currency_totals.get(currency, Decimal("0")) + amount

    months_list = [
        {
            "year": year,
            "month": month,
            "events": sorted(bucket["events"], key=lambda e: e["date"]),
            "totals": bucket["totals"],
        }
        for (year, month), bucket in sorted(groups.items())
    ]
    return {
        "horizon_months": months,
        "has_bond_details": has_bond_details,
        "currency_totals": currency_totals,
        "months": months_list,
    }
