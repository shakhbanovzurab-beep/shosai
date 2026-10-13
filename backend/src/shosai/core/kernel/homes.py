"""Data homes: where the data of an account or a company lives (target architecture §4.1, §6)."""

from enum import StrEnum


class Home(StrEnum):
    """A data home: a separate PostgreSQL cluster in its own jurisdiction.

    The value is the short code carried by the access token and by task payloads.
    The directory and data without an owner live in the EU home (ADR 0005, ADR 0010).
    Files of both homes share one bucket in Russia; the home is not part of an object
    key (ADR 0014).
    """

    RU = "ru"
    EU = "eu"
