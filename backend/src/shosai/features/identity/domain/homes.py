"""The data home of a new account, chosen by the country the person confirms (fr-7, §6)."""

import re
from dataclasses import dataclass
from typing import Final

from shosai.core.kernel.homes import Home

COUNTRY_CODE: Final = re.compile(r"[A-Z]{2}")
RUSSIA: Final = "RU"


class InvalidCountryError(ValueError):
    """The value is not an ISO 3166-1 alpha-2 code."""


@dataclass(frozen=True, slots=True)
class CountryCode:
    """An ISO 3166-1 alpha-2 code in upper case."""

    value: str

    def __post_init__(self) -> None:
        if not COUNTRY_CODE.fullmatch(self.value):
            message = "код страны — две латинские буквы ISO 3166-1"
            raise InvalidCountryError(message)


def home_for_country(country: CountryCode) -> Home:
    """Russia's accounts live in the Russian home, every other country's in the EU home."""
    return Home.RU if country.value == RUSSIA else Home.EU


def russian_visitor(country: str | None, language: str | None) -> bool:
    """Whose first data the Russian home records: Russia, an unknown country or a Russian interface.

    Only the home of a first mail follows it (152-FZ, ADR 0048); the sign-in buttons follow
    `social.visible_providers`.
    """
    russian_interface = (language or "").lower().startswith("ru")
    return country is None or country.upper() == RUSSIA or russian_interface


def home_for_visitor(country: str | None, language: str | None) -> Home:
    """The home that first records a visitor's data before they name their country."""
    return Home.RU if russian_visitor(country, language) else Home.EU
