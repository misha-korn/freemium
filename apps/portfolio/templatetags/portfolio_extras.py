"""Display helpers for portfolio templates.

Keep formatting logic out of the data layer: valuation returns raw Decimals /
fractions; these filters render them. ``None`` always renders as an em dash so
unpriced / unconvertible values stay visibly honest.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

_DASH = "—"


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@register.filter
def percent(value: object, decimals: int = 2) -> str:
    """Render a fraction (0.153) as a percentage string ('15.30%')."""
    number = _to_decimal(value)
    if number is None:
        return _DASH
    return f"{number * 100:.{int(decimals)}f}%"


@register.filter
def signed(value: object, decimals: int = 2) -> str:
    """Render a number with an explicit leading '+' for positive values."""
    number = _to_decimal(value)
    if number is None:
        return _DASH
    prefix = "+" if number > 0 else ""
    return f"{prefix}{number:.{int(decimals)}f}"


@register.filter
def money(value: object, decimals: int = 2) -> str:
    """Render a monetary amount, or an em dash when missing."""
    number = _to_decimal(value)
    if number is None:
        return _DASH
    return f"{number:,.{int(decimals)}f}"
