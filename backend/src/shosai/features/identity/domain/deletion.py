"""The deletion window and the erasure saga's rules (ID-D5, ADR 0045 point 6).

A confirmed request hides the account at once and erases it after 7 days; a sign-in in
between cancels it. The saga then runs every owner's handler, identity's last: identity
anonymises the account row, which money rows keep referencing (402-FZ), and only then frees
the address in the directory, so a new account with it cannot meet the old row's email.
"""

from collections.abc import Sequence
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

DELETION_WINDOW: Final = timedelta(days=7)
# Подтверждение — только из сессии, начатой входом не раньше 15 минут назад.
REAUTHENTICATION_WINDOW: Final = timedelta(minutes=15)
IDENTITY_OWNER: Final = "identity"
# Обезличенное имя аккаунта: ограничение длины имени требует хотя бы один символ.
ERASED_NAME: Final = "—"
ERASED_DOMAIN: Final = "deleted.invalid"


class DeletionState(StrEnum):
    """Where a deletion request is."""

    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    ERASING = "erasing"


def erased_email(user_id: UUID) -> str:
    """The placeholder address of an erased account; `.invalid` never receives mail."""
    return f"deleted-{user_id.hex}@{ERASED_DOMAIN}"


def erasure_order(owners: Sequence[str]) -> list[str]:
    """The owners in the order the saga erases them: every other owner, then identity."""
    others = sorted(owner for owner in owners if owner != IDENTITY_OWNER)
    return [*others, IDENTITY_OWNER] if IDENTITY_OWNER in owners else others
