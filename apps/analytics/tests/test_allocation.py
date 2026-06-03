from decimal import Decimal

from apps.analytics.services import allocation_by, simple_return


def test_allocation_normalises_to_one():
    alloc = allocation_by({"A": Decimal("30"), "B": Decimal("70")})
    assert alloc["A"] == Decimal("0.3")
    assert alloc["B"] == Decimal("0.7")
    assert sum(alloc.values()) == Decimal("1")


def test_allocation_handles_zero_total():
    alloc = allocation_by({"A": Decimal("0"), "B": Decimal("0")})
    assert alloc == {"A": Decimal("0"), "B": Decimal("0")}


def test_simple_return():
    assert simple_return(Decimal("1000"), Decimal("1100")) == Decimal("0.1")
    assert simple_return(Decimal("0"), Decimal("100")) == Decimal("0")
