"""Meetings of the `lead` persona: sessions, transcripts, notes, mind map, impact.

The seed writes rows directly, bypassing the processing pipeline: in production the
notes, the map, the speakers and the impact are built by the pipeline (STT, LLM, S3),
which the stand does not have. Every completed meeting has a completed run: otherwise
the draft's background "rescue" would consider the meeting abandoned and start the
pipeline.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from meetassist.features.context_graph.infrastructure.models import PcgEntity
from meetassist.features.meetings.contracts.dto import Stage, StageStatus
from meetassist.features.meetings.domain.lifecycle import STAGE_ORDER
from meetassist.features.meetings.infrastructure.impact_models import MeetingWorkspaceImpact
from meetassist.features.meetings.infrastructure.models import MeetingProcessingRun
from meetassist.features.meetings.infrastructure.speaker_models import MeetingSpeaker
from meetassist.models.meeting_map_node import MeetingMapNode
from meetassist.models.meeting_note import MeetingNote
from meetassist.models.meeting_note_action_item import MeetingNoteActionItem
from meetassist.models.session import Session
from meetassist.models.transcript_segment import TranscriptSegment
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

import meeting_content as content
from stable_ids import BUDGET_SEGMENT, MEETINGS


@dataclass(frozen=True)
class MeetingSpec:
    """A meeting: when, how long, in which state and with which content."""

    key: str
    title: str
    start: datetime
    minutes: int
    status: str = "completed"
    run_state: str = "completed"
    ephemeral: bool = False
    mcp_shared: bool = False
    speakers: tuple[str, ...] = ()
    lines: tuple[content.Line, ...] = ()
    draft: str | None = None
    enhanced: str | None = None
    tasks: tuple[tuple[str, bool, int], ...] = ()
    nodes: tuple[content.Node, ...] = ()
    impacts: tuple[content.Impact, ...] = ()
    #: Индекс кластера, которого черновик предлагает опознать как этого человека.
    candidate: tuple[int, str] | None = None
    segment_ids: dict[int, uuid.UUID] = field(default_factory=dict)


def meeting_specs(clock: datetime) -> tuple[MeetingSpec, ...]:
    """Meetings relative to the parity clock: today, yesterday, this week and earlier."""
    day = timedelta(days=1)
    today = clock.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        MeetingSpec("budget", "Планирование бюджета Q4", today + timedelta(hours=7), 47, mcp_shared=True,
                    speakers=content.BUDGET_SPEAKERS, lines=content.BUDGET_LINES, draft=content.BUDGET_DRAFT,
                    enhanced=content.BUDGET_ENHANCED, tasks=content.BUDGET_TASKS, nodes=content.BUDGET_MAP,
                    impacts=content.BUDGET_IMPACTS, candidate=(1, "Иван Петров"),
                    segment_ids={content.BUDGET_EVIDENCE_LINE: BUDGET_SEGMENT}),
        MeetingSpec("sync", "Синк команды разработки", today - day + timedelta(hours=8, minutes=30), 32,
                    speakers=content.SYNC_SPEAKERS, lines=content.SYNC_LINES, draft=content.SYNC_DRAFT),
        MeetingSpec("interview", "Интервью: бэкенд-разработчик", today - 3 * day + timedelta(hours=10), 55,
                    ephemeral=True),
        MeetingSpec("retro", "Ретро спринта 14", today - 4 * day + timedelta(hours=14), 61,
                    status="processing", run_state="transcribing"),
        MeetingSpec("demo", "Демо для клиента Acme", today - 9 * day + timedelta(hours=13), 40,
                    status="failed", run_state="failed"),
        MeetingSpec("untitled", "", today - 15 * day + timedelta(hours=16), 12),
        MeetingSpec("lawyer", "Звонок с юристом по договору", today - 23 * day + timedelta(hours=11), 25,
                    speakers=content.LAWYER_SPEAKERS, lines=content.LAWYER_LINES, draft="",
                    enhanced=content.LAWYER_ENHANCED),
        MeetingSpec("kickoff", "Кик-офф проекта «Северный ветер»", today - 37 * day + timedelta(hours=7), 70,
                    speakers=content.KICKOFF_SPEAKERS, lines=content.KICKOFF_LINES, draft="",
                    enhanced=content.KICKOFF_ENHANCED, nodes=content.KICKOFF_MAP),
        MeetingSpec("report", "Квартальный отчёт", today - 58 * day + timedelta(hours=10), 35, draft="",
                    enhanced=content.REPORT_ENHANCED),
    )


async def seed_meetings(db: AsyncSession, owner: User, clock: datetime) -> dict[str, Session]:
    """Seed the owner's meetings; return them by key."""
    sessions: dict[str, Session] = {}
    for spec in meeting_specs(clock):
        sessions[spec.key] = await _meeting(db, owner, spec)
    return sessions


async def _meeting(db: AsyncSession, owner: User, spec: MeetingSpec) -> Session:
    end = spec.start + timedelta(minutes=spec.minutes)
    session = Session(
        id=uuid.UUID(MEETINGS[spec.key]),
        title=spec.title,
        started_at=spec.start,
        ended_at=end,
        status=spec.status,
        client_device_id="parity-seed",
        user_id=owner.id,
        ephemeral=spec.ephemeral,
        mcp_shared=spec.mcp_shared,
        language="ru",
        source="import",
        created_at=spec.start,
    )
    db.add(session)
    await db.flush()
    run = _run(owner, session, spec, end)
    db.add(run)
    await db.flush()
    session.latest_run_id = run.id
    segments = _segments(session, spec)
    db.add_all(segments)
    await db.flush()
    if spec.draft is not None or spec.enhanced is not None:
        await _note(db, session, spec, segments)
    await _map(db, session, spec)
    await _speakers(db, owner, session, run, spec)
    db.add_all(_impacts(owner, session, run, spec, segments))
    await db.flush()
    return session


def _run(owner: User, session: Session, spec: MeetingSpec, end: datetime) -> MeetingProcessingRun:
    """A processing run: completed, failed, or still transcribing on its first attempt."""
    finished = end + timedelta(minutes=3)
    stages: dict[str, dict[str, object]] = {}
    for position, stage in enumerate(STAGE_ORDER):
        stages[stage.value] = _stage_record(spec.run_state, stage, position, finished)
    return MeetingProcessingRun(
        session_id=session.id,
        user_id=owner.id,
        state=spec.run_state,
        source="import",
        idempotency_key=f"parity:{spec.key}",
        stage_state=stages,
        attempt=1,
        last_error="stt_failed" if spec.run_state == "failed" else None,
        completed_at=finished if spec.run_state == "completed" else None,
        created_at=end,
    )


def _stage_record(run_state: str, stage: Stage, position: int, finished: datetime) -> dict[str, object]:
    if run_state == "completed":
        return {"status": StageStatus.SUCCEEDED.value, "attempt": 1, "duration_ms": 1500 + 700 * position,
                "error_code": None, "finished_at": finished.isoformat()}
    if stage is Stage.AUDIO_INGESTION:
        return {"status": StageStatus.SUCCEEDED.value, "attempt": 1, "duration_ms": 1800,
                "error_code": None, "finished_at": finished.isoformat()}
    if stage is Stage.TRANSCRIPTION:
        failed = run_state == "failed"
        # Первая попытка: подпись «попытка N» черновик показывает со второй, и по-русски
        # она откатывается на английский «attempt 2» (дефект, инвентарь — Findings).
        return {"status": (StageStatus.FAILED if failed else StageStatus.RUNNING).value, "attempt": 1,
                "duration_ms": 12_000, "error_code": "stt_failed" if failed else None, "finished_at": None}
    return {"status": StageStatus.PENDING.value, "attempt": 0, "duration_ms": None,
            "error_code": None, "finished_at": None}


def _segments(session: Session, spec: MeetingSpec) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for index, line in enumerate(spec.lines):
        following = spec.lines[index + 1].offset_s if index + 1 < len(spec.lines) else line.offset_s + 9
        started = session.started_at + timedelta(seconds=line.offset_s)
        duration_ms = (following - line.offset_s) * 1000 - 500
        segments.append(
            TranscriptSegment(
                id=spec.segment_ids.get(index, uuid.uuid4()),
                session_id=session.id,
                speaker_label=spec.speakers[line.speaker],
                speaker_idx=line.speaker,
                started_at=started,
                ended_at=started + timedelta(milliseconds=duration_ms),
                duration_ms=duration_ms,
                text=line.text,
                whisper_confidence=0.94,
                checksum=hashlib.sha256(f"{spec.key}:{index}:{line.text}".encode()).hexdigest(),
                language="ru",
                source="import",
                created_at=started,
            )
        )
    return segments


async def _note(db: AsyncSession, session: Session, spec: MeetingSpec, segments: list[TranscriptSegment]) -> None:
    note = MeetingNote(session_id=session.id, draft_markdown=spec.draft or "", enhanced_markdown=spec.enhanced,
                       version=1, created_at=session.ended_at, updated_at=session.ended_at)
    db.add(note)
    await db.flush()
    for position, (text, done, line) in enumerate(spec.tasks):
        db.add(MeetingNoteActionItem(note_id=note.id, text=text, done=done, source_segment_id=segments[line].id,
                                     position=position, created_at=session.ended_at))


async def _map(db: AsyncSession, session: Session, spec: MeetingSpec) -> None:
    """Map nodes in order: a parent always comes before its child."""
    created: list[MeetingMapNode] = []
    for position, node in enumerate(spec.nodes):
        row = MeetingMapNode(
            session_id=session.id,
            node_type=node.kind,
            title=node.title,
            start_offset_ms=node.offset_s * 1000,
            parent_node_id=None if node.parent is None else created[node.parent].id,
            confidence=0.9,
            origin="ai",
            position=position,
            created_at=session.ended_at,
        )
        db.add(row)
        await db.flush()
        created.append(row)


async def _speakers(db: AsyncSession, owner: User, session: Session, run: MeetingProcessingRun,
                    spec: MeetingSpec) -> None:
    for index, label in enumerate(spec.speakers):
        lines = [line for line in spec.lines if line.speaker == index]
        speaker = MeetingSpeaker(session_id=session.id, run_id=run.id, user_id=owner.id, cluster_idx=index,
                                 display_label=label, identity_status="unknown", segments_count=len(lines),
                                 total_ms=len(lines) * 8000, created_at=session.ended_at)
        if spec.candidate is not None and spec.candidate[0] == index:
            person = PcgEntity(user_id=owner.id, kind="person", name=spec.candidate[1],
                               norm_key=spec.candidate[1].lower(), aliases=[], confidence=0.82,
                               source_kind="meeting", source_id=str(session.id), created_at=session.ended_at)
            db.add(person)
            await db.flush()
            speaker.person_entity_id = person.id
            speaker.identity_status = "candidate"
            speaker.identity_confidence = 0.82
            speaker.identity_source = "transcript"
        db.add(speaker)


def _impacts(owner: User, session: Session, run: MeetingProcessingRun, spec: MeetingSpec,
             segments: list[TranscriptSegment]) -> list[MeetingWorkspaceImpact]:
    return [
        MeetingWorkspaceImpact(
            id=uuid.uuid4(),
            session_id=session.id,
            run_id=run.id,
            user_id=owner.id,
            target_kind=impact.target_kind,
            target_id=impact.target_id,
            operation=impact.operation,
            before_state=impact.before,
            after_state=impact.after,
            confidence=impact.confidence,
            status=impact.status,
            policy_decision=impact.policy,
            evidence_segment_id=segments[impact.evidence].id,
            source_text=spec.lines[impact.evidence].text,
            dedup_key=impact.dedup_key,
            applied_at=session.ended_at if impact.status == "applied" else None,
            created_at=session.ended_at,
        )
        for impact in spec.impacts
    ]
