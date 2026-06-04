"""Foreign-exchange conversion for multi-currency aggregation (Stage 2).

Deliberately simple and HONEST: rates come from ``settings.FX_RATES`` (a static
stop-gap), plus identity for same-currency conversion and a ``1/x`` inverse.
When a rate is unavailable we return ``None`` rather than fabricating a number —
callers degrade gracefully (per-currency figures stay exact; base-currency
totals are simply marked unavailable).

A live FX provider can later replace ``_rate_table`` without touching callers.
Money is Decimal — never float.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings

# 8 decimal places — matches the project-wide money precision.
_QUANT = Decimal("0.00000001")


def _rate_table(rates: dict | None) -> dict[str, dict[str, Decimal]]:
    """Normalise a ``{from: {to: rate}}`` mapping to upper-case Decimal rates."""
    source = settings.FX_RATES if rates is None else rates
    table: dict[str, dict[str, Decimal]] = {}
    for base, pairs in (source or {}).items():
        table[str(base).upper()] = {
            str(quote).upper(): Decimal(str(value)) for quote, value in pairs.items()
        }
    return table


def get_rate(
    from_currency: str, to_currency: str, rates: dict | None = None
) -> Decimal | None:
    """Return the rate to convert 1 unit of ``from`` into ``to``, or None.

    Resolution order: identity (same currency) → direct rate → inverse rate.
    """
    src = (from_currency or "").upper()
    dst = (to_currency or "").upper()
    if not src or not dst:
        return None
    if src == dst:
        return Decimal("1")

    table = _rate_table(rates)
    direct = table.get(src, {}).get(dst)
    if direct is not None:
        return direct

    inverse = table.get(dst, {}).get(src)
    if inverse:  # non-zero
        return Decimal("1") / inverse
    return None


def convert(
    amount: Decimal, from_currency: str, to_currency: str, rates: dict | None = None
) -> Decimal | None:
    """Convert ``amount`` between currencies, or None if no rate is available."""
    rate = get_rate(from_currency, to_currency, rates)
    if rate is None:
        return None
    return (amount * rate).quantize(_QUANT)
