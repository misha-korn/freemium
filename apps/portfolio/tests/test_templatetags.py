from decimal import Decimal

from apps.portfolio.templatetags.portfolio_extras import money, percent, signed


def test_percent_formats_fraction():
    assert percent(Decimal("0.153")) == "15.30%"
    assert percent(Decimal("-0.05")) == "-5.00%"


def test_percent_handles_float_and_none():
    assert percent(0.1) == "10.00%"
    assert percent(None) == "—"
    assert percent("") == "—"


def test_signed_adds_plus_for_positive():
    assert signed(Decimal("12.5")) == "+12.50"
    assert signed(Decimal("-3")) == "-3.00"
    assert signed(Decimal("0")) == "0.00"
    assert signed(None) == "—"


def test_money_groups_thousands():
    assert money(Decimal("1234567.5")) == "1,234,567.50"
    assert money(None) == "—"
