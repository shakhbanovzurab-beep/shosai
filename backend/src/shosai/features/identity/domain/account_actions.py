"""What the admin may do to an account, and from which states (SM-12, ADR 0049).

Block freezes an active account, unblock returns a frozen one. An account already in the
target state stays as it is and the action writes nothing; one banned before ADR 0049,
being deleted, erased or moved is not touched.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.registration import DirectoryState


class AccountAction(StrEnum):
    """The admin's action on an account."""

    BLOCK = "block"
    UNBLOCK = "unblock"


@dataclass(frozen=True, slots=True)
class Transition:
    """The states an action starts from and the state it leaves."""

    allowed_from: frozenset[AccountState]
    target: AccountState
    # Блокировка завершает все сессии; разблокировка их не возвращает.
    ends_sessions: bool


TRANSITIONS: Final = {
    AccountAction.BLOCK: Transition(
        frozenset({AccountState.ACTIVE}), AccountState.FROZEN, ends_sessions=True
    ),
    AccountAction.UNBLOCK: Transition(
        frozenset({AccountState.FROZEN}), AccountState.ACTIVE, ends_sessions=False
    ),
}

# Как действие меняет строку каталога в ЕС: из каких состояний и в какое.
DIRECTORY_CHANGES: Final = {
    AccountAction.BLOCK: (frozenset({DirectoryState.ACTIVE}), DirectoryState.FROZEN),
    AccountAction.UNBLOCK: (frozenset({DirectoryState.FROZEN}), DirectoryState.ACTIVE),
}
