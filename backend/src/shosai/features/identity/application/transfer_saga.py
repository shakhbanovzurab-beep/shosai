"""The account transfer saga, step by step (§6, identity plan §3.6).

The journal lives in the home the account leaves. Each step does its work, then moves the
journal on by compare-and-set (`transfer_journal.record`): a cancel recorded meanwhile
wins, and a repeat of a finished step is a no-op. Every step is idempotent — a crash after
its work and before its record repeats it to the same result.

Until the switch the account is `transferring`: its marker in Valkey refuses every token,
so nothing is written to the source while it is copied; each step renews the marker. After
the switch the new home bumps the token version, and the old tokens stop for good.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

import structlog

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS, AccountDataHandler
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import AccountTransferred
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.deletion import erasure_order
from shosai.features.identity.domain.transfer import (
    FINISHED,
    FORWARD,
    MOVABLE,
    TransferStep,
    copy_order,
)
from shosai.features.identity.infrastructure.account_markers import AccountMarker, AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.transfer_journal import (
    NO_CHANGE,
    Journal,
    JournalChange,
    claim_open,
    read_journal,
    record,
    record_copied,
)
from shosai.features.identity.infrastructure.transfer_metrics import TransferMetrics

log = structlog.stdlib.get_logger(__name__)
type Handlers = Mapping[str, AccountDataHandler]


class MarkerUnavailableError(ConnectionError):
    """Valkey did not take the account marker; the step waits for the next delivery."""


@dataclass(frozen=True, slots=True)
class SagaServices:
    """What the saga reaches: both homes, the handlers, the directory, markers and events."""

    transactions: HomeTransactions
    ports: PortDirectory
    directory: Directory
    markers: AccountMarkers
    outbox: EventOutbox
    metrics: TransferMetrics


class TransferSaga:
    """Runs the transfers whose journal is in a home."""

    def __init__(self, services: SagaServices) -> None:
        self._services = services

    async def start_due(self, home: Home) -> list[UUID]:
        """Claim the home's open transfers; each claim is one more attempt."""
        ids, oldest = await claim_open(self._services.transactions, home)
        self._services.metrics.oldest(home, oldest)
        return ids

    async def run(self, home: Home, transfer_id: UUID) -> None:
        """Take the transfer through its steps until it is done or cancelled."""
        while await self.step(home, transfer_id):
            pass

    async def step(self, home: Home, transfer_id: UUID) -> bool:
        """One step of the transfer; False once it has finished."""
        journal = await read_journal(self._services.transactions, home, transfer_id)
        if journal is None or journal.step in FINISHED:
            return False
        handlers = {item.owner: item for item in self._services.ports.all(ACCOUNT_DATA_HANDLERS)}
        done = False
        try:
            await self._do(journal, handlers)
            done = True
        finally:
            self._services.metrics.step(journal.step, "done" if done else "failed")
        return True

    async def _do(self, journal: Journal, handlers: Handlers) -> None:
        match journal.step:
            case TransferStep.FREEZE:
                await self._freeze(journal)
            case TransferStep.COPY:
                await self._copy(journal, handlers)
            case TransferStep.VERIFY:
                await self._verify(journal, handlers)
            case TransferStep.SWITCH:
                await self._services.directory.move(journal.user_id, journal.target)
                await self._advance(journal)
            case TransferStep.BUMP:
                await self._bump(journal)
            case TransferStep.PURGE:
                for owner in erasure_order(list(handlers)):
                    await handlers[owner].purge(journal.account(journal.source))
                await self._advance(journal)
            case TransferStep.CANCELLING:
                await self._cancel(journal, handlers)
            case TransferStep.DONE | TransferStep.CANCELLED:
                return

    async def _freeze(self, journal: Journal) -> None:
        async with self._services.transactions.begin(journal.scope()) as session:
            user = await session.get(User, journal.user_id, with_for_update=True)
            state = None if user is None else AccountState(user.state)
            if user is None or (state not in MOVABLE and state is not AccountState.TRANSFERRING):
                conflict = JournalChange(error="account_state_conflict")
                await record(session, journal, TransferStep.CANCELLED, conflict)
                return
            prior = journal.prior_state or state
            user.state = AccountState.TRANSFERRING
            await record(session, journal, TransferStep.COPY, JournalChange(prior_state=prior))
        await self._hold(journal)

    async def _copy(self, journal: Journal, handlers: Handlers) -> None:
        await self._hold(journal)
        for owner in copy_order(list(handlers)):
            if owner in journal.copied_owners:
                continue
            await handlers[owner].copy(journal.account(journal.source), journal.target)
            if not await record_copied(self._services.transactions, journal, owner):
                return
        await self._advance(journal)

    async def _verify(self, journal: Journal, handlers: Handlers) -> None:
        await self._hold(journal)
        source: dict[str, Mapping[str, str]] = {}
        mismatched = []
        for owner, handler in sorted(handlers.items()):
            source[owner] = await handler.manifest(journal.account(journal.source))
            if source[owner] != await handler.manifest(journal.account(journal.target)):
                mismatched.append(owner)
        if mismatched:
            log.error("Перенос отменяется: данные в домах разошлись", owners=mismatched)
            mismatch = JournalChange(error="manifest_mismatch")
            await self._advance(journal, TransferStep.CANCELLING, mismatch)
            return
        await self._advance(journal, change=JournalChange(manifest=source))

    async def _bump(self, journal: Journal) -> None:
        scope = TenancyScope(journal.target, journal.user_id)
        async with self._services.transactions.begin(scope) as session:
            user = await session.get(User, journal.user_id, with_for_update=True)
            if user is None:
                message = "аккаунта нет в целевом доме после переключения каталога"
                raise RuntimeError(message)
            if user.state == AccountState.TRANSFERRING:
                user.state = journal.prior_state or AccountState.ACTIVE
                user.token_version += 1
                moved = AccountTransferred(
                    user_id=user.id, from_home=journal.source, to_home=journal.target
                )
                await self._services.outbox.add(session, moved)
            marker = AccountMarker(user.token_version, AccountState(user.state))
        await self._mark(journal.user_id, marker)
        await self._advance(journal)

    async def _cancel(self, journal: Journal, handlers: Handlers) -> None:
        for owner in erasure_order(list(handlers)):
            await handlers[owner].purge(journal.account(journal.target))
        async with self._services.transactions.begin(journal.scope()) as session:
            user = await session.get(User, journal.user_id, with_for_update=True)
            if user is not None and user.state == AccountState.TRANSFERRING:
                user.state = journal.prior_state or AccountState.ACTIVE
            marker = (
                None
                if user is None
                else AccountMarker(user.token_version, AccountState(user.state))
            )
        if marker is not None:
            await self._mark(journal.user_id, marker)
        await self._advance(journal, TransferStep.CANCELLED)

    async def _hold(self, journal: Journal) -> None:
        """Renew the source account's marker before a step's work."""
        transactions = self._services.transactions
        async with transactions.begin(journal.scope(), read_only=True) as session:
            user = await session.get(User, journal.user_id)
        if user is not None:
            marker = AccountMarker(user.token_version, AccountState(user.state))
            await self._mark(journal.user_id, marker)

    async def _mark(self, user_id: UUID, marker: AccountMarker) -> None:
        if not await self._services.markers.write(user_id, marker):
            raise MarkerUnavailableError

    async def _advance(
        self, journal: Journal, step: TransferStep | None = None, change: JournalChange = NO_CHANGE
    ) -> None:
        async with self._services.transactions.begin(journal.scope()) as session:
            await record(session, journal, step or FORWARD[journal.step], change)
