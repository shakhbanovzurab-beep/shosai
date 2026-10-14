"""Asking for an account transfer, cancelling it, reading it (identity plan §3.4, §6).

Only an operator asks, and only while the owner has opened transfers after the legal
review (§22). One transfer of an account is open at a time; a cancel is accepted until the
directory switch, after which the saga only goes forward. Each request and cancel leaves
an audit event in the transaction that records it.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Operator, OperatorActed, OperatorAction
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.transfer import CANCELLABLE, MOVABLE, TransferStep
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.transfer_records import OPEN, HomeTransfer


@dataclass(frozen=True, slots=True)
class TransferView:
    """A transfer as an operator reads it."""

    id: UUID
    user_id: UUID
    from_home: Home
    to_home: Home
    step: TransferStep
    requested_at: datetime
    finished_at: datetime | None
    error_code: str | None


class Transfers:
    """Operators' requests and cancels of transfers."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: Directory,
        outbox: EventOutbox,
        *,
        allowed: bool,
    ) -> None:
        self._transactions = transactions
        self._directory = directory
        self._outbox = outbox
        self._allowed = allowed

    async def request(self, actor: Operator, user_id: UUID, to_home: Home) -> TransferView:
        """Queue the transfer of the account to the other home."""
        if not self._allowed:
            raise AppError("transfers_closed", HTTPStatus.CONFLICT)
        source = await self._directory.home_of(user_id)
        if source is None:
            raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
        if source is to_home:
            raise AppError("same_home", HTTPStatus.CONFLICT)
        transfer_id = new_id()
        async with self._transactions.begin(TenancyScope(source, user_id)) as session:
            user = await session.get(User, user_id)
            if user is None:
                raise AppError("user_not_found", HTTPStatus.NOT_FOUND)
            if AccountState(user.state) not in MOVABLE:
                raise AppError("account_state_conflict", HTTPStatus.CONFLICT)
            queued = await session.scalar(
                insert(HomeTransfer)
                .values(
                    id=transfer_id, user_id=user_id, from_home=source.value, to_home=to_home.value,
                    step=TransferStep.FREEZE.value, requested_by=actor.principal.user_id,
                    run_at=datetime.now(UTC),
                )
                .on_conflict_do_nothing(
                    index_elements=[HomeTransfer.user_id], index_where=text(OPEN)
                )
                .returning(HomeTransfer.id)
            )  # fmt: skip
            if queued is None:
                raise AppError("transfer_in_progress", HTTPStatus.CONFLICT)
            requested = OperatorAction.ACCOUNT_TRANSFER_REQUESTED
            await self._audit(session, actor, user_id, source, requested)
        return await self.view(transfer_id)

    async def cancel(self, actor: Operator, transfer_id: UUID) -> TransferView:
        """Cancel a transfer that has not switched the directory yet."""
        found = await self.view(transfer_id)
        async with self._transactions.begin(TenancyScope(found.from_home)) as session:
            cancelled = await session.scalar(
                update(HomeTransfer)
                .where(
                    HomeTransfer.id == transfer_id,
                    HomeTransfer.step.in_([step.value for step in CANCELLABLE]),
                )
                .values(step=TransferStep.CANCELLING.value)
                .returning(HomeTransfer.user_id)
            )
            if cancelled is None:
                raise AppError("transfer_not_cancellable", HTTPStatus.CONFLICT)
            action = OperatorAction.ACCOUNT_TRANSFER_CANCELLED
            await self._audit(session, actor, cancelled, found.from_home, action)
        return await self.view(transfer_id)

    async def view(self, transfer_id: UUID) -> TransferView:
        """The transfer, from whichever home holds its journal."""
        found = await asyncio.gather(*(self._read(home, transfer_id) for home in Home))
        for view in found:
            if view is not None:
                return view
        raise AppError("transfer_not_found", HTTPStatus.NOT_FOUND)

    async def _read(self, home: Home, transfer_id: UUID) -> TransferView | None:
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            row = await session.scalar(select(HomeTransfer).where(HomeTransfer.id == transfer_id))
        if row is None:
            return None
        return TransferView(
            row.id, row.user_id, Home(row.from_home), Home(row.to_home), TransferStep(row.step),
            row.requested_at, row.finished_at, row.error_code,
        )  # fmt: skip

    async def _audit(
        self,
        session: AsyncSession,
        actor: Operator,
        user_id: UUID,
        home: Home,
        action: OperatorAction,
    ) -> None:
        event = OperatorActed(
            operator_id=actor.principal.user_id, target_user_id=user_id, target_home=home,
            action=action,
        )  # fmt: skip
        await self._outbox.add(session, event)
