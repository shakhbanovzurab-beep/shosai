"""The erasure saga: after the window, every owner's handler erases its part (ID-D5).

A sweep claims the deletions whose `erase_at` passed and moves each account to `deleting`;
its task then queues one erasure task per account. An unfinished erasure comes due again
when the claim's lease ends, so the sweep queues it again. The erasure runs the handlers
bound to `core.account_data_handlers`, identity's last, records each finished owner in the
journal and skips it on a repeat. Then every owner reads its part again, and anything
left is counted and logged by id for the nfr-13 monitor; a check that cannot read fails
the task, which runs it again. Last, one transaction deletes the journal row and
announces `AccountDeleted`. Handlers are idempotent: a duplicate erases nothing twice.
"""

from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import (
    ACCOUNT_DATA_HANDLERS,
    AccountDataHandler,
    AccountRef,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.schedule.due_rows import DueRows, claim_due
from shosai.core.tasks.declaration import (
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.identity.contracts import AccountDeleted
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.deletion import DeletionState, erasure_order
from shosai.features.identity.infrastructure.deletion_metrics import DeletionMetrics
from shosai.features.identity.infrastructure.deletion_records import AccountDeletion
from shosai.features.identity.infrastructure.records import User

SWEEP_LIMIT: Final = 20
# Дольше дедлайна задачи: пока она жива, обход её не дублирует.
SWEEP_LEASE: Final = timedelta(minutes=30)
DELETIONS: Final = AccountDeletion.metadata.tables["account_deletions"]
DUE: Final = DueRows(
    table=DELETIONS,
    key=DELETIONS.c.user_id,
    run_at=DELETIONS.c.run_at,
    pending=DELETIONS.c.state.in_((DeletionState.SCHEDULED.value, DeletionState.ERASING.value)),
)
ERASE_ACCOUNT: Final = TaskDeclaration(
    name="identity.erase_account",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=20),
    retry=RetryPolicy(max_deliveries=5, retry_on=TRANSIENT_FAILURES),
    kind=TaskKind.WORK,
)
log = structlog.stdlib.get_logger(__name__)


class Erasure:
    """Starts the erasure of due accounts and runs it owner by owner."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        outbox: EventOutbox,
        metrics: DeletionMetrics,
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._outbox = outbox
        self._metrics = metrics

    async def start_due(self, home: Home) -> list[UUID]:
        """Begin the home's erasures whose window ended; the accounts to erase now."""
        now = datetime.now(UTC)
        async with self._transactions.begin(TenancyScope(home)) as session:
            claimed = await claim_due(session, DUE, limit=SWEEP_LIMIT, lease=SWEEP_LEASE)
            ready = [
                row.user_id
                for row in claimed
                if row.state == DeletionState.ERASING or await _begin(session, row.user_id, now)
            ]
            oldest = await session.scalar(
                select(func.min(AccountDeletion.started_at)).where(
                    AccountDeletion.state == DeletionState.ERASING.value
                )
            )
        self._metrics.oldest(home, (now - oldest).total_seconds() if oldest else 0.0)
        return ready

    async def erase(self, account: AccountRef) -> None:
        """Run every owner's handler not yet recorded, then finish the deletion."""
        done = await self._erased_owners(account)
        if done is None:
            return
        handlers = {handler.owner: handler for handler in self._ports.all(ACCOUNT_DATA_HANDLERS)}
        for owner in erasure_order(list(handlers)):
            if owner not in done:
                await self._run(handlers[owner], account)
                await self._record(account, owner)
        await self._check(account, list(handlers.values()))
        await self._finish(account)

    async def _check(self, account: AccountRef, handlers: list[AccountDataHandler]) -> None:
        """Read every owner's part again (nfr-13): a remain pages, the erasure still ends."""
        for handler in handlers:
            remains = await handler.remains(account)
            if remains:
                self._metrics.leftovers(handler.owner, len(remains))
                log.error(
                    "После стирания у владельца остались данные человека",
                    handler=handler.owner,
                    remains=list(remains),
                    user_id=str(account.user_id),
                    home=account.home.value,
                )

    async def _erased_owners(self, account: AccountRef) -> frozenset[str] | None:
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            deletion = await session.get(AccountDeletion, account.user_id)
        if deletion is None or deletion.state != DeletionState.ERASING:
            return None
        return frozenset(deletion.erased_owners)

    async def _run(self, handler: AccountDataHandler, account: AccountRef) -> None:
        erased = False
        try:
            await handler.erase(account)
            erased = True
        finally:
            self._metrics.step(handler.owner, "erased" if erased else "failed")

    async def _record(self, account: AccountRef, owner: str) -> None:
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            await session.execute(
                update(AccountDeletion)
                .where(
                    AccountDeletion.user_id == account.user_id,
                    func.array_position(AccountDeletion.erased_owners, owner).is_(None),
                )
                .values(erased_owners=func.array_append(AccountDeletion.erased_owners, owner))
            )

    async def _finish(self, account: AccountRef) -> None:
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            finished = await session.scalar(
                delete(AccountDeletion)
                .where(
                    AccountDeletion.user_id == account.user_id,
                    AccountDeletion.state == DeletionState.ERASING.value,
                )
                .returning(AccountDeletion.user_id)
            )
            if finished is not None:
                await self._outbox.add(session, AccountDeleted(user_id=account.user_id))
        if finished is not None:
            log.info("Аккаунт стёрт", user_id=str(account.user_id), home=account.home.value)


async def _begin(session: AsyncSession, user_id: UUID, now: datetime) -> bool:
    """Move a scheduled account to `deleting`; False while a sign-in holds its row.

    The account row is taken without waiting: a sign-in that holds it is cancelling the
    deletion, and the next claim finds the request cancelled.
    """
    user = await session.scalar(
        select(User).where(User.id == user_id).with_for_update(skip_locked=True)
    )
    if user is None:
        return False
    if user.state != AccountState.DELETION_SCHEDULED:
        log.warning("Стирание не начато: аккаунт не ждёт удаления", state=user.state)
        return False
    user.state = AccountState.DELETING
    await session.execute(
        update(AccountDeletion)
        .where(AccountDeletion.user_id == user_id)
        .values(state=DeletionState.ERASING.value, started_at=now)
    )
    return True
