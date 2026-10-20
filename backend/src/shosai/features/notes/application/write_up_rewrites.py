"""A rewrite of a meeting's write-up with a template (plan §3.4 flow 6; api-design).

Whoever may manage the meeting asks for its write-up again by a template: the summary is
written anew and the sections laid out by the template, over the findings the notes list
now, which keep their ids. A person's own template is read in their scope and copied into
the run, since the stage runs in the meeting's scope. A request is applied once per
`Idempotency-Key` for 24 hours: a retry answers the same run, the same key with another
body is 422. A meeting whose notes are not written yet answers 409 `notes_not_ready`.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.lifecycle import RunStarter
from shosai.features.notes.application.run_rows import ensure_run
from shosai.features.notes.application.visibility import meeting_scope
from shosai.features.notes.application.write_up_layout import layout_of
from shosai.features.notes.contracts import MeetingNotFoundError
from shosai.features.notes.domain.runs import RunSource, Stage, idempotency_key
from shosai.features.notes.domain.write_up import SectionPlan, layout_json
from shosai.features.notes.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
)
from shosai.features.notes.infrastructure.notes_records import NotesRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

REWRITES: Final = EffectScope("notes.write_up_rewrite", timedelta(hours=24))
log = structlog.stdlib.get_logger(__name__)


class TemplateNotFoundError(AppError):
    """No such template the person may use: neither shipped nor theirs (404)."""

    def __init__(self) -> None:
        super().__init__("template_not_found", HTTPStatus.NOT_FOUND)


class NotesNotReadyError(AppError):
    """The meeting's notes are not written yet, so there is nothing to rewrite (409)."""

    def __init__(self) -> None:
        super().__init__("notes_not_ready", HTTPStatus.CONFLICT)


class RewriteRequest(BaseModel):
    """What a rewrite asks for; its print tells a retry from another request."""

    meeting_id: UUID
    template_id: str


class RewriteAccepted(BaseModel):
    """The run that rewrites the notes."""

    run_id: UUID


class WriteUpRewrites:
    """Starts rewrites of meetings' write-ups."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, EffectLedger, RunStarter],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._effects, self._starter = collaborators
        self._clock = clock

    async def rewrite(self, principal: Principal, request: RewriteRequest, client_key: str) -> UUID:
        """Start the rewrite once per key; the run's id, also for a retry."""
        key = account_key(principal.user_id, client_key)
        effect = EffectKey(REWRITES, key, fingerprint_of(request))
        scope, layout = await self.prepare(principal, request)
        async with self._transactions.begin(scope) as session:
            outcome = await self._effects.once(
                session,
                effect,
                RewriteAccepted,
                lambda: self.start_in(session, principal, (request, layout), key),
            )
        if not outcome.replayed:
            await self.kick(scope, request.meeting_id, outcome.outcome.run_id)
        return outcome.outcome.run_id

    async def prepare(
        self, principal: Principal, request: RewriteRequest
    ) -> tuple[TenancyScope, tuple[SectionPlan, ...]]:
        """The scope the meeting changes in and the template's layout.

        A person's own template is read in their scope, and a company's meeting changes in
        the company's: both are read here, before the meeting's transaction.
        """
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            layout = await layout_of(session, request.template_id)
            if layout is None:
                raise TemplateNotFoundError
            scope = await meeting_scope(session, policy, principal.scope(), request.meeting_id)
        return scope, layout

    async def kick(self, scope: TenancyScope, meeting_id: UUID, run_id: UUID) -> None:
        """Send the started rewrite's stage, after its transaction committed."""
        await self._starter.kick(scope, run_id, Stage.WRITE_UP)
        log.info("Запись встречи переписывается", meeting_id=str(meeting_id))

    async def start_in(
        self,
        session: AsyncSession,
        principal: Principal,
        asked: tuple[RewriteRequest, tuple[SectionPlan, ...]],
        key: str,
    ) -> RewriteAccepted:
        """The rewrite's run, in the caller's transaction of the meeting's scope."""
        request, layout = asked
        policy = self._ports.get(ACCESS_POLICY)
        meeting = await session.scalar(
            select(MeetingRecord)
            .where(
                MeetingRecord.id == request.meeting_id,
                policy.manageable(MEETING_RESOURCE, Viewer(principal.user_id)),
                MeetingRecord.deleted_at.is_(None),
            )
            .with_for_update(of=MeetingRecord)
        )
        if meeting is None:
            raise MeetingNotFoundError
        notes = await session.get(NotesRecord, meeting.id)
        if notes is None or notes.write_up is None:
            raise NotesNotReadyError
        chosen = {"template_id": request.template_id, "sections": layout_json(layout)}
        run_id = await ensure_run(
            session,
            meeting,
            RunSource.REGENERATE,
            idempotency_key(RunSource.REGENERATE, request_key=key),
            layout=chosen,
        )
        meeting.template_id, meeting.latest_run_id = request.template_id, run_id
        meeting.updated_at = self._clock()
        return RewriteAccepted(run_id=run_id)
