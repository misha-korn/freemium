"""Provider interface + Quote / SymbolMatch value objects."""
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


@dataclass(frozen=True)
class SymbolMatch:
    """A search hit: a tradable symbol and its display name."""

    ticker: str
    name: str


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

    def get_name(self, symbol: str) -> str | None:
        """Return the instrument's display name (company / security), or None.

        Default: unknown. Providers that can resolve names override this.
        """
        return None

    def search(self, query: str) -> list[SymbolMatch]:
        """Return tradable symbols matching ``query`` (ticker or name).

        Default: no search. Providers with a lookup endpoint override this.
        """
        return []
