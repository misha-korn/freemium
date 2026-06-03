"""Provider interface + Quote value object."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Quote:
    """An immutable price observation. ``price`` is Decimal — never float."""

    symbol: str
    price: Decimal
    currency: str
    as_of: datetime
    source: str


class QuoteProvider(ABC):
    """Abstract market-data provider."""

    name: str = "base"

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote | None:
        """Return the latest quote for ``symbol`` or None if unavailable."""
        raise NotImplementedError

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Batch helper; subclasses may override with a true bulk call."""
        quotes: dict[str, Quote] = {}
        for symbol in symbols:
            quote = self.get_quote(symbol)
            if quote is not None:
                quotes[symbol] = quote
        return quotes
