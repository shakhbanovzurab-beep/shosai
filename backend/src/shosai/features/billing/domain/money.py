"""Money in Shosai's three currencies: minor units, never converted, never mixed (ADR 0054).

Prices are set by the admin in each currency; a sum, a discount or a refund stays in one
currency, and amounts of two currencies are never added.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

# Потолок цены в минорных единицах — как в форме тарифа кабинета.
MAX_MINOR: Final = 1_000_000_000


class Currency(StrEnum):
    """A currency a plan is priced and paid in."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class MixedCurrenciesError(ValueError):
    """Two amounts of different currencies were combined."""


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """An amount in minor units of one currency (kopecks, cents)."""

    currency: Currency
    minor: int

    def __post_init__(self) -> None:
        if not 0 <= self.minor <= MAX_MINOR:
            message = f"сумма {self.minor} вне 0…{MAX_MINOR} минорных единиц"
            raise ValueError(message)

    def plus(self, other: Money) -> Money:
        """The sum of two amounts of one currency."""
        if other.currency is not self.currency:
            raise MixedCurrenciesError
        return Money(self.currency, self.minor + other.minor)

    def minus(self, other: Money) -> Money:
        """The difference, never below zero."""
        if other.currency is not self.currency:
            raise MixedCurrenciesError
        return Money(self.currency, max(self.minor - other.minor, 0))


@dataclass(frozen=True, slots=True)
class Prices:
    """A plan's price for one period in each currency: all zero (free) or all positive."""

    amounts: Mapping[Currency, int]

    def __post_init__(self) -> None:
        if set(self.amounts) != set(Currency):
            message = "цена тарифа задаётся во всех трёх валютах"
            raise ValueError(message)
        values = list(self.amounts.values())
        if not all(0 <= value <= MAX_MINOR for value in values):
            message = f"цена вне 0…{MAX_MINOR} минорных единиц"
            raise ValueError(message)
        if any(values) and not all(values):
            message = "за период цена либо нулевая во всех валютах, либо положительная во всех"
            raise ValueError(message)

    @property
    def free(self) -> bool:
        """Zero in every currency."""
        return not any(self.amounts.values())

    def of(self, currency: Currency) -> Money:
        """The price in one currency."""
        return Money(currency, self.amounts[currency])


FREE: Final = Prices({currency: 0 for currency in Currency})
