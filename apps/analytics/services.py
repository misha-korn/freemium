"""Analytics service layer — pure, framework-free, Decimal-aware.

Returns / diversification / risk helpers consumed by the dashboard in later
stages. Functions take plain data and return plain data so they are trivially
unit-testable without the database.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

DAYS_PER_YEAR = 365.0
_MAX_NEWTON_ITERATIONS = 100
_MAX_BISECTION_ITERATIONS = 200
_TOLERANCE = 1e-9


def simple_return(invested: Decimal, current_value: Decimal) -> Decimal:
    """Total return as a fraction: (current - invested) / invested."""
    if invested == 0:
        return Decimal("0")
    return (current_value - invested) / invested


def allocation_by(weights: dict[str, Decimal]) -> dict[str, Decimal]:
    """Normalise raw weights into shares of the total (each in 0..1)."""
    total = sum(weights.values(), Decimal("0"))
    if total == 0:
        return {key: Decimal("0") for key in weights}
    return {key: value / total for key, value in weights.items()}


def _npv(rate: float, cashflows: list[tuple[date, Decimal]], t0: date) -> float:
    """Net present value of dated cashflows at an annual ``rate``."""
    total = 0.0
    for when, amount in cashflows:
        years = (when - t0).days / DAYS_PER_YEAR
        total += float(amount) / ((1.0 + rate) ** years)
    return total


def xirr(cashflows: list[tuple[date, Decimal]], guess: float = 0.1) -> float:
    """Money-weighted annualised return (internal rate of return) for dated flows.

    Sign convention: outflows/investments are NEGATIVE, inflows/current value
    are POSITIVE. Requires at least one of each. Uses Newton-Raphson with a
    bisection fallback. Raises ValueError if it cannot bracket a root.
    """
    if len(cashflows) < 2:
        raise ValueError("xirr requires at least two cashflows")

    flows = sorted(cashflows, key=lambda item: item[0])
    amounts = [float(amount) for _, amount in flows]
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        raise ValueError("xirr requires both positive and negative cashflows")

    t0 = flows[0][0]

    # --- Newton-Raphson ---
    rate = guess
    for _ in range(_MAX_NEWTON_ITERATIONS):
        value = _npv(rate, flows, t0)
        derivative = (_npv(rate + 1e-6, flows, t0) - value) / 1e-6
        if derivative == 0:
            break
        new_rate = rate - value / derivative
        if new_rate <= -0.999999:
            break
        if abs(new_rate - rate) < 1e-8:
            return new_rate
        rate = new_rate

    # --- Bisection fallback on [-0.999999, 10] ---
    low, high = -0.999999, 10.0
    f_low, f_high = _npv(low, flows, t0), _npv(high, flows, t0)
    if f_low * f_high > 0:
        raise ValueError("xirr failed to converge (no sign change in bracket)")
    for _ in range(_MAX_BISECTION_ITERATIONS):
        mid = (low + high) / 2.0
        f_mid = _npv(mid, flows, t0)
        if abs(f_mid) < _TOLERANCE:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0
