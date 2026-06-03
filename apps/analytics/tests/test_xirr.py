from datetime import date
from decimal import Decimal

import pytest

from apps.analytics.services import xirr


def test_xirr_one_year_ten_percent():
    flows = [
        (date(2023, 1, 1), Decimal("-1000")),
        (date(2024, 1, 1), Decimal("1100")),
    ]
    assert abs(xirr(flows) - 0.10) < 0.01


def test_xirr_requires_sign_change():
    with pytest.raises(ValueError):
        xirr([(date(2023, 1, 1), Decimal("-100")), (date(2024, 1, 1), Decimal("-50"))])


def test_xirr_requires_two_flows():
    with pytest.raises(ValueError):
        xirr([(date(2023, 1, 1), Decimal("-100"))])
