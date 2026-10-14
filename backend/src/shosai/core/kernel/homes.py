"""Data homes: where the data of an account or a company lives (target architecture §4.1, §6)."""

from enum import StrEnum


class Home(StrEnum):
    """A data home: a separate PostgreSQL cluster in its own jurisdiction.

    The value is the short code carried by the access token and by task payloads.
    The directory and data without an owner live in the EU home (ADR 0005, ADR 0010).
    Each home has its own bucket; the home is not part of an object key: an object lives
    in the bucket of its pointer's home (ADR 0044).
    """

    RU = "ru"
    EU = "eu"
