"""The transfer journal's reads and writes, in the home the account leaves (§6).

A step moves the journal on with a compare-and-set: only if the journal still names the
step that ran. A cancel recorded meanwhile wins, and a step repeated after a crash finds
the journal moved and changes nothing. The sweep claims open transfers by `run_at`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.schedule.due_rows import DueRows, claim_due
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.transfer import FINISHED, TransferStep
from shosai.features.identity.infrastructure.transfer_records import HomeTransfer

SWEEP_LIMIT: Final = 10
# Дольше дедлайна задачи переноса: пока она жива, обход её не дублирует.
SWEEP_LEASE: Final = timedelta(minutes=30)
JOURNAL: Final = HomeTransfer.metadata.tables["home_transfers"]
DUE: Final = DueRows(
    table=JOURNAL,
    key=JOURNAL.c.id,
    run_at=JOURNAL.c.run_at,
    pending=JOURNAL.c.step.notin_([step.value for step in FINISHED]),
)


@dataclass(frozen=True, slots=True)
class Journal:
    """A transfer as a step reads it."""

    id: UUID
    user_id: UUID
    source: Home
    target: Home
    step: TransferStep
    prior_state: AccountState | None
    copied_owners: frozenset[str]

    def account(self, home: Home) -> AccountRef:
        """The account in one of the two homes."""
        return AccountRef(self.user_id, home)

    def scope(self) -> TenancyScope:
        """Where the journal and the account start: the source home."""
        return TenancyScope(self.source, self.user_id)


@dataclass(frozen=True, slots=True)
class JournalChange:
    """What a step writes into the journal beside the next step."""

    prior_state: AccountState | None = None
    manifest: Mapping[str, Mapping[str, str]] | None = None
    error: str | None = None


NO_CHANGE: Final = JournalChange()


async def read_journal(
    transactions: HomeTransactions, home: Home, transfer_id: UUID
) -> Journal | None:
    """The transfer of this id in the home, or None."""
    async with transactions.begin(TenancyScope(home), read_only=True) as session:
        row = await session.get(HomeTransfer, transfer_id)
    if row is None:
        return None
    return Journal(
        row.id, row.user_id, Home(row.from_home), Home(row.to_home), TransferStep(row.step),
        None if row.prior_state is None else AccountState(row.prior_state),
        frozenset(row.copied_owners),
    )  # fmt: skip


async def record(
    session: AsyncSession, journal: Journal, step: TransferStep, change: JournalChange = NO_CHANGE
) -> bool:
    """Move the journal on, only if it still names the step that ran; whether it moved."""
    values: dict[str, object] = {"step": step.value}
    if change.prior_state is not None:
        values["prior_state"] = change.prior_state.value
    if change.manifest is not None:
        values["manifest"] = {owner: dict(digests) for owner, digests in change.manifest.items()}
    if change.error is not None:
        values["error_code"] = change.error
    if step in FINISHED:
        values["finished_at"] = datetime.now(UTC)
    moved = await session.scalar(
        update(HomeTransfer)
        .where(HomeTransfer.id == journal.id, HomeTransfer.step == journal.step.value)
        .values(values)
        .returning(HomeTransfer.id)
    )
    return moved is not None


async def record_copied(transactions: HomeTransactions, journal: Journal, owner: str) -> bool:
    """Note an owner as copied while the journal still says copy; whether it was noted."""
    async with transactions.begin(journal.scope()) as session:
        noted = await session.scalar(
            update(HomeTransfer)
            .where(HomeTransfer.id == journal.id, HomeTransfer.step == journal.step.value)
            .values(copied_owners=func.array_append(HomeTransfer.copied_owners, owner))
            .returning(HomeTransfer.id)
        )
    return noted is not None


async def claim_open(transactions: HomeTransactions, home: Home) -> tuple[list[UUID], float]:
    """Claim the home's open transfers, one attempt each; and the oldest one's age."""
    now = datetime.now(UTC)
    async with transactions.begin(TenancyScope(home)) as session:
        claimed = await claim_due(session, DUE, limit=SWEEP_LIMIT, lease=SWEEP_LEASE)
        ids = [row.id for row in claimed]
        await session.execute(
            update(HomeTransfer)
            .where(HomeTransfer.id.in_(ids))
            .values(attempts=HomeTransfer.attempts + 1)
        )
        oldest = await session.scalar(
            select(func.min(HomeTransfer.requested_at)).where(
                HomeTransfer.step.notin_([step.value for step in FINISHED])
            )
        )
    return ids, (now - oldest).total_seconds() if oldest else 0.0


async def purge_finished(transactions: HomeTransactions, home: Home, older_than: datetime) -> int:
    """Drop the journals of transfers that finished before `older_than`; how many went."""
    async with transactions.begin(TenancyScope(home)) as session:
        purged = await session.scalars(
            delete(HomeTransfer)
            .where(HomeTransfer.finished_at < older_than)
            .returning(HomeTransfer.id)
        )
        return len(purged.all())
