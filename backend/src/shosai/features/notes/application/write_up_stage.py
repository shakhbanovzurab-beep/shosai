"""The write-up stage: Leo's notes by a template, the map and `notes.meeting.notes_ready`.

The layout is the one a person chose for a rewrite, copied into its run, else the
meeting's template — a shipped one or the owner's own — or Leo's layout when the meeting
has none or its template is gone. A rewrite lists the findings the current notes list, so
every finding keeps its id; any other run lists its own. Only the summary is a model's
text, written from the findings and the end of the transcript that fits the call — cut
from the head by whole lines, so the closing lines are always read. The notes, the map,
the meeting's next revision and the event are written in one transaction; a delivery that
finds the notes written by its run calls nothing and writes nothing (inv-8). A desktop
recording's run rewrites the write-up only while it is Leo's automatic one: once the person
chose a template or rewrote it, the recording leaves it as it is (MT-D3).
"""

import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.application.found_items import listed
from shosai.features.notes.application.notes_model import NotesModel, Question
from shosai.features.notes.application.notes_studio import NotesStudio, notes_studio
from shosai.features.notes.application.pipeline import StageFailedError, StageWork
from shosai.features.notes.application.stage_reads import (
    MEETING_GONE,
    archived_spoken,
    cross_border,
    present_meeting,
    spoken_lines,
)
from shosai.features.notes.application.stored_findings import findings_of
from shosai.features.notes.application.write_up_layout import layout_of
from shosai.features.notes.contracts.events import NotesReady
from shosai.features.notes.domain.findings import Finding, FindingKind
from shosai.features.notes.domain.mind_map import project_map
from shosai.features.notes.domain.runs import RunSource
from shosai.features.notes.domain.templates import ENHANCED, LEO_LAYOUT, SectionKind
from shosai.features.notes.domain.transcript_text import SpokenLine, rendered, tail
from shosai.features.notes.domain.write_up import (
    ListedFinding,
    SectionPlan,
    builtin_layout,
    layout_from_json,
    map_json,
    write_up_document,
    written_sections,
)
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.notes_metrics import NotesCall
from shosai.features.notes.infrastructure.notes_records import NotesRecord
from shosai.features.notes.infrastructure.prompts import (
    OWN_FOCUS,
    SUMMARY_FOCUS,
    SUMMARY_INSTRUCTIONS,
    TRANSCRIPT_END_HEADER,
    SummaryAnswer,
)
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive

SUMMARY_TOKENS: Final = 800
SUMMARY_MAX: Final = 4_000
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Draft:
    """What the write-up is made of: the template, the findings and the transcript's end."""

    template_id: str
    layout: tuple[SectionPlan, ...]
    findings_run: UUID | None
    findings: list[tuple[UUID, Finding]]
    closing: list[SpokenLine]
    consent: bool
    studio: NotesStudio = field(default_factory=NotesStudio)


def summary_text(answer: SummaryAnswer | None) -> str | None:
    """The summary without control characters, within its bound; None when empty."""
    if answer is None:
        return None
    text = "".join(c for c in answer.summary if c in "\n" or unicodedata.category(c) != "Cc")
    return text.strip()[:SUMMARY_MAX] or None


def focus_of(plan: SectionPlan) -> str:
    """What the summary of this section is about."""
    if plan.title is not None:
        return OWN_FOCUS.replace("<title>", plan.title)
    return SUMMARY_FOCUS.get(plan.heading_code or "", SUMMARY_FOCUS[SectionKind.SUMMARY.value])


class WriteUpStage:
    """Writes a meeting's notes for a run."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, EventOutbox, NotesModel, TranscriptArchive],
        budget: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox, self._model, self._archive = collaborators
        self._budget = budget
        self._clock = clock

    async def run(self, work: StageWork) -> None:
        """Write the notes once per run."""
        draft = await self._read(work)
        if draft is None:
            return
        summary = None
        plan = next((p for p in draft.layout if p.kind is SectionKind.SUMMARY), None)
        if plan is not None:
            summary = summary_text(await self._summary(work, draft, plan))
        await self._write(work, draft, summary)

    async def _read(self, work: StageWork) -> Draft | None:
        """What the notes need, or None when this run already wrote them."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            notes = await session.get(NotesRecord, work.meeting_id)
            if notes is not None and notes.write_up_run_id == work.run_id:
                return None
            if kept_by_person(work.source, notes):
                log.info("Запись встречи выбрана человеком: прогон записи её не трогает")
                return None
            meeting = await present_meeting(session, work.meeting_id)
            template_id, layout = await self._layout(session, meeting, work.run_id)
            findings_run = (
                (notes.findings_run_id if notes is not None else None)
                if work.source is RunSource.REGENERATE
                else work.run_id
            )
            findings = await findings_of(session, meeting.id, findings_run)
            summarised = any(plan.kind is SectionKind.SUMMARY for plan in layout)
            archived = meeting.transcript_archive_key if summarised else None
            lines = await spoken_lines(session, meeting) if summarised and archived is None else []
            consent = summarised and await cross_border(session, self._ports, meeting.user_id)
            # Модель зовёт только раздел итогов: без него studio не спрашивается.
            studio = (
                await notes_studio(self._ports, session, work.scope, legacy=self._model.legacy)
                if summarised
                else NotesStudio()
            )
        if archived is not None:
            lines = await archived_spoken(self._archive, work.scope.home, archived)
        return Draft(template_id, layout, findings_run, findings, lines, consent, studio)

    async def _layout(
        self, session: AsyncSession, meeting: MeetingRecord, run_id: UUID
    ) -> tuple[str, tuple[SectionPlan, ...]]:
        run = await session.get(RunRecord, run_id)
        if run is not None and run.layout is not None:
            return str(run.layout["template_id"]), layout_from_json(run.layout["sections"])
        template_id = meeting.template_id or ENHANCED
        try:
            layout = await layout_of(session, template_id)
        except ValueError:
            log.exception("Шаблон встречи не читается", meeting_id=str(meeting.id))
            layout = None
        if layout is None:
            log.warning("Шаблона встречи нет: запись по раскладке Leo", meeting_id=str(meeting.id))
            return ENHANCED, builtin_layout(LEO_LAYOUT)
        return template_id, layout

    async def _summary(
        self, work: StageWork, draft: Draft, plan: SectionPlan
    ) -> SummaryAnswer | None:
        findings = listed([finding for _, finding in draft.findings])
        room = self._budget - len(findings) - len(TRANSCRIPT_END_HEADER)
        closing = "\n".join(map(rendered, tail(draft.closing, room)))
        question = Question(
            NotesCall.SUMMARY, 0,
            draft.studio.styled(SUMMARY_INSTRUCTIONS.replace("<focus>", focus_of(plan))),
            f"{findings}\n\n{TRANSCRIPT_END_HEADER}\n{closing}", SUMMARY_TOKENS,
        )  # fmt: skip
        return await self._model.ask(
            work, question, SummaryAnswer, consent=draft.consent, studio=draft.studio
        )

    async def _write(self, work: StageWork, draft: Draft, summary: str | None) -> None:
        now = self._clock()
        async with self._transactions.begin(work.scope) as session:
            meeting = await session.scalar(
                select(MeetingRecord).where(MeetingRecord.id == work.meeting_id).with_for_update()
            )
            if meeting is None or meeting.deleted_at is not None:
                raise StageFailedError(MEETING_GONE)
            notes = await session.get(NotesRecord, meeting.id, with_for_update=True)
            if notes is not None and notes.write_up_run_id == work.run_id:
                return
            if notes is None:
                notes = NotesRecord(
                    session_id=meeting.id, user_id=meeting.user_id, org_id=meeting.org_id
                )
                session.add(notes)
            findings = [finding for _, finding in draft.findings]
            sections = written_sections(
                draft.layout, summary, [ListedFinding(i, f.kind) for i, f in draft.findings]
            )
            notes.write_up = write_up_document(draft.template_id, sections)
            notes.write_up_template, notes.write_up_run_id = draft.template_id, work.run_id
            notes.findings_run_id = draft.findings_run
            notes.write_up_automatic = work.source is not RunSource.REGENERATE
            notes.map = map_json(project_map(meeting.title, findings))
            notes.write_up_written_at = notes.updated_at = now
            meeting.notes_revision += 1
            meeting.updated_at = now
            await self._outbox.add(session, ready(meeting, work.run_id, findings))
        log.info(
            "Запись встречи готова",
            run_id=str(work.run_id),
            revision=meeting.notes_revision,
            summary=summary is not None,
        )


def kept_by_person(source: RunSource, notes: NotesRecord | None) -> bool:
    """A desktop recording rewrites only Leo's automatic write-up (MT-D3)."""
    return source is RunSource.RECORDING and notes is not None and not notes.write_up_automatic


def ready(meeting: MeetingRecord, run_id: UUID, findings: list[Finding]) -> NotesReady:
    """The event of the meeting's new notes: its revision and the findings it lists."""
    counts = Counter(finding.kind for finding in findings)
    return NotesReady(
        meeting_id=meeting.id, run_id=run_id, user_id=meeting.user_id, org_id=meeting.org_id,
        revision=meeting.notes_revision, key_points=counts[FindingKind.KEY_POINT],
        decisions=counts[FindingKind.DECISION], action_items=counts[FindingKind.ACTION_ITEM],
        promises=counts[FindingKind.PROMISE], risks=counts[FindingKind.RISK],
        questions=counts[FindingKind.QUESTION],
    )  # fmt: skip
