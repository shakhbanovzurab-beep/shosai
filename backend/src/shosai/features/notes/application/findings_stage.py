"""The findings stage: what a meeting produced, each with its evidence (plan §3.4 flow 6).

The transcript goes to the model in one call when it fits the call's budget, else in
windows of whole lines overlapping by eight lines, asked at once, each part under its own
effect key. A window whose answer is unreadable twice is lost — counted, logged, its
findings missing from the notes — unless every window is lost, which fails the attempt
for a retry. Findings of several windows go through one merging pass that keeps one of
each said twice; a lost merge keeps them all. The findings are written in one transaction
under the run and the meeting's next revision, after the provider calls; a delivery that
finds the run's findings written calls nothing and writes nothing (inv-8).
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.application.found_items import (
    kept_by_merge,
    listed,
    raw_findings,
    without_repeats,
)
from shosai.features.notes.application.notes_model import NotesModel, Question
from shosai.features.notes.application.pipeline import StageFailedError, StageWork
from shosai.features.notes.application.stage_reads import (
    MEETING_GONE,
    TRANSCRIPT_EMPTY,
    cross_border,
    present_meeting,
    spoken_lines,
)
from shosai.features.notes.domain.findings import Finding, checked_finding
from shosai.features.notes.domain.transcript_text import SpokenLine, rendered, windows
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.notes_metrics import NotesCall
from shosai.features.notes.infrastructure.notes_records import FindingRecord
from shosai.features.notes.infrastructure.prompts import (
    FINDINGS_INSTRUCTIONS,
    MERGE_INSTRUCTIONS,
    PART_HEADER,
    FindingsAnswer,
    MergeAnswer,
)

ANSWERS_UNREADABLE: Final = "model_answer_unreadable"
# Сорок находок с цитатами на кириллице — до 6–7 тысяч токенов ответа.
WINDOW_TOKENS: Final = 8_000
MERGE_TOKENS: Final = 1_000
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MeetingText:
    """What the stage read of the meeting: its start, length, lines and the owner's consent."""

    started_at: datetime
    length_ms: int
    lines: list[SpokenLine]
    consent: bool


class FindingsStage:
    """Extracts a meeting's findings for a run."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, NotesModel],
        budget: int,
    ) -> None:
        self._transactions = transactions
        self._ports, self._model = collaborators
        self._budget = budget

    async def run(self, work: StageWork) -> None:
        """Find, check, merge and write the meeting's findings once per run."""
        text = await self._read(work)
        if text is None:
            return
        parts = windows(text.lines, self._budget)
        answers = await self._asked(work, text, parts)
        if all(answer is None for answer in answers):
            raise StageFailedError(ANSWERS_UNREADABLE)
        found: list[Finding] = []
        for answer, window in zip(answers, parts, strict=True):
            if answer is None:
                continue
            for raw in raw_findings(answer.findings, window):
                finding = checked_finding(
                    raw, meeting_ms=text.length_ms, meeting_started_at=text.started_at
                )
                if finding is not None:
                    found.append(finding)
        findings = without_repeats(found)
        if len(parts) > 1 and len(findings) > 1:
            findings = await self._merged(work, (text.consent, len(parts)), findings)
        lost = sum(answer is None for answer in answers)
        await self._write(work, findings)
        log.info(
            "Находки встречи записаны",
            run_id=str(work.run_id),
            findings=len(findings),
            windows=len(parts),
            windows_lost=lost,
        )

    async def _read(self, work: StageWork) -> MeetingText | None:
        """The meeting's text, or None when this run's findings are already written."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            if await self._written(session, work):
                return None
            meeting = await present_meeting(session, work.meeting_id)
            lines = await spoken_lines(session, meeting)
            consent = await cross_border(session, self._ports, meeting.user_id)
        if not lines:
            raise StageFailedError(TRANSCRIPT_EMPTY)
        length = max(meeting.seconds * 1000, *(line.end_ms for line in lines))
        return MeetingText(meeting.started_at, length, lines, consent)

    async def _asked(
        self, work: StageWork, text: MeetingText, parts: Sequence[Sequence[SpokenLine]]
    ) -> list[FindingsAnswer | None]:
        instructions = FINDINGS_INSTRUCTIONS.replace(
            "<meeting_date>", text.started_at.date().isoformat()
        )
        questions = [
            Question(
                NotesCall.WINDOW, number, instructions,
                "\n".join(
                    (PART_HEADER.format(part=number + 1, parts=len(parts)), *map(rendered, window))
                ),
                WINDOW_TOKENS,
            )
            for number, window in enumerate(parts)
        ]  # fmt: skip
        asked = await asyncio.gather(
            *(self._model.ask(work, q, FindingsAnswer, consent=text.consent) for q in questions),
            return_exceptions=True,
        )
        answers: list[FindingsAnswer | None] = []
        for answer in asked:
            # Сбой провайдера в любом окне — сбой попытки: движок повторит стадию.
            if isinstance(answer, BaseException):
                raise answer
            answers.append(answer)
        return answers

    async def _merged(
        self, work: StageWork, asked: tuple[bool, int], findings: list[Finding]
    ) -> list[Finding]:
        """The findings after the merging pass, asked as the part after the last window."""
        consent, part = asked
        question = Question(
            NotesCall.MERGE, part, MERGE_INSTRUCTIONS, listed(findings), MERGE_TOKENS
        )
        answer = await self._model.ask(work, question, MergeAnswer, consent=consent)
        return list(findings) if answer is None else kept_by_merge(findings, answer.keep)

    async def _written(self, session: AsyncSession, work: StageWork) -> bool:
        # По встрече и прогону: запрос идёт по индексу находок встречи, а не по всей таблице.
        found = await session.scalar(
            select(FindingRecord.id)
            .where(FindingRecord.session_id == work.meeting_id, FindingRecord.run_id == work.run_id)
            .limit(1)
        )
        return found is not None

    async def _write(self, work: StageWork, findings: Sequence[Finding]) -> None:
        async with self._transactions.begin(work.scope) as session:
            meeting = await session.scalar(
                select(MeetingRecord).where(MeetingRecord.id == work.meeting_id).with_for_update()
            )
            if meeting is None or meeting.deleted_at is not None:
                raise StageFailedError(MEETING_GONE)
            if await self._written(session, work):
                return
            revision = meeting.notes_revision + 1
            session.add_all(
                FindingRecord(
                    id=new_id(), session_id=meeting.id, user_id=meeting.user_id,
                    org_id=meeting.org_id, run_id=work.run_id, revision=revision,
                    position=position, kind=f.kind.value, text=f.text, topic=f.topic,
                    owner_speaker=f.owner_speaker, owner_name=f.owner_name, due_on=f.due_on,
                    start_ms=f.evidence.start_ms, end_ms=f.evidence.end_ms, quote=f.evidence.quote,
                )
                for position, f in enumerate(findings)
            )  # fmt: skip
