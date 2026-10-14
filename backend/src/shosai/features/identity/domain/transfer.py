"""The account transfer saga between the data homes (§6, identity plan §3.6).

Steps, in order: freeze the account in its home, copy every owner's part to the other
home with objects under the same keys, verify both homes' manifests, switch the directory
in the EU, bump the token version in the new home, purge the old home. Until the switch a
cancel removes the copies and unfreezes the account; after it the saga only goes forward.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.deletion import IDENTITY_OWNER


class TransferStep(StrEnum):
    """The next step of a transfer, or how it ended."""

    FREEZE = "freeze"
    COPY = "copy"
    VERIFY = "verify"
    SWITCH = "switch"
    BUMP = "bump"
    PURGE = "purge"
    CANCELLING = "cancelling"
    DONE = "done"
    CANCELLED = "cancelled"


FINISHED: Final = frozenset({TransferStep.DONE, TransferStep.CANCELLED})
# До переключения каталога перенос отменяем: источник ещё нетронут.
CANCELLABLE: Final = frozenset({TransferStep.FREEZE, TransferStep.COPY, TransferStep.VERIFY})
FORWARD: Final = {
    TransferStep.FREEZE: TransferStep.COPY,
    TransferStep.COPY: TransferStep.VERIFY,
    TransferStep.VERIFY: TransferStep.SWITCH,
    TransferStep.SWITCH: TransferStep.BUMP,
    TransferStep.BUMP: TransferStep.PURGE,
    TransferStep.PURGE: TransferStep.DONE,
}
# Переносится только аккаунт, которым можно пользоваться или который заморожен оператором.
MOVABLE: Final = frozenset({AccountState.ACTIVE, AccountState.FROZEN})


def copy_order(owners: Sequence[str]) -> list[str]:
    """Identity first: every other owner's rows reference the account row it copies."""
    others = sorted(owner for owner in owners if owner != IDENTITY_OWNER)
    return [IDENTITY_OWNER, *others] if IDENTITY_OWNER in owners else others
