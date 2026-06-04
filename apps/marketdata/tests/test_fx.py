from decimal import Decimal

from apps.marketdata import fx

RATES = {"USD": {"RUB": "90"}, "EUR": {"USD": "1.08"}}


def test_identity_rate_is_one():
    assert fx.get_rate("USD", "USD") == Decimal("1")


def test_direct_rate():
    assert fx.get_rate("USD", "RUB", RATES) == Decimal("90")


def test_inverse_rate_is_derived():
    rate = fx.get_rate("RUB", "USD", RATES)
    assert rate is not None
    assert abs(rate - (Decimal("1") / Decimal("90"))) < Decimal("0.0000001")


def test_missing_rate_returns_none():
    assert fx.get_rate("USD", "JPY", RATES) is None
    assert fx.get_rate("", "USD", RATES) is None


def test_convert_uses_rate_and_quantizes():
    converted = fx.convert(Decimal("10"), "USD", "RUB", RATES)
    assert converted == Decimal("900.00000000")


def test_convert_same_currency_is_identity():
    assert fx.convert(Decimal("123.45"), "RUB", "RUB", RATES) == Decimal("123.45000000")


def test_convert_missing_rate_returns_none():
    assert fx.convert(Decimal("10"), "USD", "JPY", RATES) is None


def test_rates_are_case_insensitive():
    assert fx.get_rate("usd", "rub", RATES) == Decimal("90")
