"""How many accounts each home holds, for the platform operator's Leo (agent plan AG-D5).

Counts only, never a person: the accounts of a home by state, and those registered in the
last days. Each home is read in its own platform transaction, as the admin's search reads it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey


@dataclass(frozen=True, slots=True)
class HomeAccounts:
    """One home's accounts: by state, and how many registered in the period."""

    home: Home
    by_state: Mapping[str, int]
    registered: int


class AccountCounts(Protocol):
    """Counts the accounts of every home."""

    async def counts(self, days: int) -> Sequence[HomeAccounts]:
        """Each home's accounts by state, and those registered in the last `days` days."""
        ...


ACCOUNT_COUNTS: Final = PortKey[AccountCounts]("identity.account_counts")
