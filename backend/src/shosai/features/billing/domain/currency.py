"""The currency a person pays in, decided by the server from their country (draft rule).

Russia pays in roubles, the countries of the euro area and their neighbours in euros, the
rest of the world in dollars. An account without a country pays as its home suggests:
roubles in the Russian home, dollars in the EU one. The client's choice is never trusted.
"""

from typing import Final

from shosai.features.billing.domain.money import Currency

EURO_COUNTRIES: Final = frozenset(
    {
        "AD", "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
        "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "ME", "MT", "NL", "NO",
        "PL", "PT", "RO", "SE", "SI", "SK", "SM", "VA",
    }
)  # fmt: skip


def currency_for_country(country: str | None) -> Currency:
    """The currency of a country's ISO 3166-1 alpha-2 code; dollars when unknown."""
    code = (country or "").upper()
    if code == "RU":
        return Currency.RUB
    if code in EURO_COUNTRIES:
        return Currency.EUR
    return Currency.USD


def account_currency(country: str | None, *, russian_home: bool) -> Currency:
    """The currency of an account: by its country, else by its home."""
    if country:
        return currency_for_country(country)
    return Currency.RUB if russian_home else Currency.USD
