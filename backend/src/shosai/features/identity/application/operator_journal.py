"""The admin's actions on a person's data in other slices, into the EU audit log (nfr-17).

A slice records what the admin did in its own transaction of the person's home: the action
becomes `identity.operator.acted` there, and its EU delivery appends the row, as the
account actions do. Only ids and codes travel.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef
from shosai.core.events.outbox import EventOutbox
from shosai.features.identity.contracts import OperatorActed, OperatorAction


class OperatorJournal:
    """The `identity.operator_audit` port: the admin's action as an outbox event."""

    def __init__(self, outbox: EventOutbox) -> None:
        self._outbox = outbox

    async def acted(
        self,
        session: AsyncSession,
        target: AccountRef,
        action: OperatorAction,
        subject_id: UUID | None = None,
    ) -> None:
        """Record the action in the caller's transaction of the person's home."""
        event = OperatorActed(
            target_user_id=target.user_id, target_home=target.home, action=action,
            subject_id=subject_id,
        )  # fmt: skip
        await self._outbox.add(session, event)
