"""Forward income forecast — Tier 3 (#9).

Projects expected future income over the next ``months``, per currency:

- **Bond coupons** — *scheduled* (deterministic from ``BondDetail``).
- **Stock dividends** — *estimated* from the imported ``AssetDividend`` history
  (cadence × latest per-share × shares; see ``dividend_estimate``). These are
  marked as estimates in the result so the UI never presents them as facts.

Also reports the trailing-12-month dividend yield-on-cost per currency. Figures
stay per-currency and are never summed across currencies. Money is Decimal.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.marketdata.models import AssetDividend

from . import bonds, dividend_estimate
from .models import BondDetail
from .services import compute_positions

if TYPE_CHECKING:
    from datetime import date

    from .models import Portfolio

_MONEY = Decimal("0.01")
DEFAULT_HORIZON_MONTHS = 12
_DIVIDEND_ASSET_TYPES = ("STOCK", "ETF", "FUND")


def income_forecast(
    portfolio: Portfolio, *, months: int = DEFAULT_HORIZON_MONTHS, as_of: date | None = None
) -> dict:
    """Expected income (scheduled coupons + estimated dividends) over ``months``.

    Shape::

        {
          "horizon_months": int,
          "has_events": bool,
          "has_estimates": bool,            # any estimated stock dividend
          "currency_totals": {cur: Decimal},
          # trailing-12m income + yield-on-cost (fraction) per currency:
          "annual_dividends": {cur: {"amount": Decimal, "yoc": Decimal|None}},
          "months": [ {year, month, events: [
              {asset, date, amount, currency, kind, estimate}], totals} ],
        }
    """
    today = as_of or timezone.now().date()
    end = today + relativedelta(months=months)
    positions = compute_positions(portfolio)

    groups: dict[tuple[int, int], dict] = {}
    currency_totals: dict[str, Decimal] = {}
    annual_dividends: dict[str, Decimal] = {}
    invested_by_currency: dict[str, Decimal] = {}
    has_estimates = False

    def add_event(when, asset, amount, currency, kind, estimate):
        key = (when.year, when.month)
        bucket = groups.setdefault(key, {"events": [], "totals": {}})
        bucket["events"].append(
            {
                "asset": asset, "date": when, "amount": amount,
                "currency": currency, "kind": kind, "estimate": estimate,
            }
        )
        bucket["totals"][currency] = bucket["totals"].get(currency, Decimal("0")) + amount
        currency_totals[currency] = currency_totals.get(currency, Decimal("0")) + amount

    # --- Bonds: scheduled coupons ----------------------------------------- #
    bond_positions = [p for p in positions if p.asset.asset_type == "BOND"]
    bond_details = {
        b.asset_id: b
        for b in BondDetail.objects.filter(
            asset_id__in=[p.asset.id for p in bond_positions]
        )
    }
    for pos in bond_positions:
        detail = bond_details.get(pos.asset.id)
        if detail is None:
            continue
        for coupon in bonds.upcoming_coupons(detail, today, end):
            amount = (coupon["amount"] * pos.quantity).quantize(_MONEY)
            add_event(coupon["date"], pos.asset, amount, pos.asset.currency, "coupon", False)

    # --- Stocks/ETFs: estimated dividends --------------------------------- #
    stock_positions = [p for p in positions if p.asset.asset_type in _DIVIDEND_ASSET_TYPES]
    records_by_asset: dict[int, list[AssetDividend]] = {}
    for record in AssetDividend.objects.filter(
        asset_id__in=[p.asset.id for p in stock_positions]
    ).order_by("asset_id", "ex_date"):
        records_by_asset.setdefault(record.asset_id, []).append(record)

    for pos in stock_positions:
        records = records_by_asset.get(pos.asset.id, [])
        if not records:
            continue
        currency = records[-1].currency or pos.asset.currency
        # Trailing-12m income (a real figure) feeds the yield.
        annual_ps = dividend_estimate.trailing_annual_per_share(records, today)
        annual_amount = (annual_ps * pos.quantity).quantize(_MONEY)
        if annual_amount > 0:
            annual_dividends[currency] = annual_dividends.get(currency, Decimal("0")) + annual_amount
            invested_by_currency[currency] = (
                invested_by_currency.get(currency, Decimal("0")) + pos.invested
            )
        # Forward estimate.
        for est in dividend_estimate.estimate_upcoming(records, pos.quantity, today, end):
            has_estimates = True
            add_event(est["date"], pos.asset, est["amount"], est["currency"], "dividend", True)

    # Merge amount + yield-on-cost per currency so the template needs no
    # dict-by-variable lookup. Yield is None when there's no cost basis.
    annual_summary = {
        cur: {
            "amount": annual,
            "yoc": (annual / invested_by_currency[cur])
            if invested_by_currency.get(cur)
            else None,
        }
        for cur, annual in annual_dividends.items()
    }

    months_list = [
        {
            "year": year, "month": month,
            "events": sorted(bucket["events"], key=lambda e: e["date"]),
            "totals": bucket["totals"],
        }
        for (year, month), bucket in sorted(groups.items())
    ]
    return {
        "horizon_months": months,
        "has_events": bool(months_list),
        "has_estimates": has_estimates,
        "currency_totals": currency_totals,
        "annual_dividends": annual_summary,
        "months": months_list,
    }
