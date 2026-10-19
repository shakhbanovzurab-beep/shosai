"""The live transcript's store, written by capture's drain (§8.1, §11.1, §14 rule 5).

A batch may hold lines of many meetings of many people. Their facts come in one call past
row-level security (`meetings_live_facts`); personal meetings' lines are stored in one
transaction, each company's in its own scope. A line is `(meeting, seq)`: a replay
conflicts and is ignored, equal texts are two lines. A line of a meeting that is gone or
not kept is refused and counted; one longer than a line may be is cut and counted. A
line drained after its meeting ended clears the meeting's settled mark, so the sweep
looks at it again (inv-7). A batch that fails is counted, logged with its size and
raised for capture to retry; its lines are never dropped silently.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy import Uuid, bindparam, func, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.contracts import AppendOutcome, LiveLine, StoredLine
from shosai.features.meetings.domain.meetings import MeetingStatus
from shosai.features.meetings.domain.transcript import (
    SIDE_SPEAKER,
    TAIL_MAX,
    LineOrigin,
    fitted_text,
    offset_ms,
)
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.meetings.infrastructure.transcript_metrics import (
    LineOutcome,
    TranscriptMetrics,
)

FACTS_SQL: Final = text(
    "SELECT id, org_id, started_at, kept, status, gone FROM meetings_live_facts(:ids)"
).bindparams(bindparam("ids", type_=ARRAY(Uuid())))
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _Facts:
    org_id: UUID | None
    started_at: datetime
    ended: bool


class LiveTranscript:
    """The `meetings.transcript_store` binding."""

    def __init__(self, transactions: HomeTransactions, metrics: TranscriptMetrics) -> None:
        self._transactions = transactions
        self._metrics = metrics

    async def append(self, home: Home, lines: Sequence[LiveLine]) -> AppendOutcome:
        """Store a batch; replays are ignored and refused lines counted, never raised."""
        if not lines:
            return AppendOutcome(0, 0, 0)
        try:
            return await self._append(home, lines)
        except Exception:
            self._metrics.lines(LineOutcome.FAILED, len(lines))
            log.exception("Пачка строк расшифровки не сохранена", home=home.value, lines=len(lines))
            raise

    async def tail(
        self, session: AsyncSession, meeting_id: UUID, limit: int
    ) -> Sequence[StoredLine]:
        """The meeting's last lines, oldest first, at most `TAIL_MAX`."""
        started = select(MeetingRecord.started_at).where(MeetingRecord.id == meeting_id)
        rows = await session.scalars(
            select(TranscriptLineRecord)
            .where(
                TranscriptLineRecord.session_id == meeting_id,
                TranscriptLineRecord.meeting_started_at == started.scalar_subquery(),
            )
            .order_by(TranscriptLineRecord.seq.desc())
            .limit(max(0, min(limit, TAIL_MAX)))
        )
        return [stored_line(row) for row in reversed(rows.all())]

    async def _append(self, home: Home, lines: Sequence[LiveLine]) -> AppendOutcome:
        ids = sorted({line.meeting_id for line in lines})
        async with self._transactions.begin(TenancyScope(home)) as session:
            found = (await session.execute(FACTS_SQL, {"ids": ids})).all()
            facts = {
                row.id: _Facts(row.org_id, row.started_at, row.status != MeetingStatus.ACTIVE.value)
                for row in found
                if row.kept and not row.gone
            }
            groups, refused, cut = _grouped(lines, facts)
            stored = await _insert(session, groups.pop(None, []))
            await _unsettle(session, [m for m, f in facts.items() if f.ended and f.org_id is None])
        for org_id, rows in groups.items():
            async with self._transactions.begin(TenancyScope(home, org_id=org_id)) as session:
                stored += await _insert(session, rows)
                await _unsettle(
                    session, [m for m, f in facts.items() if f.ended and f.org_id == org_id]
                )
        replayed = len(lines) - refused - stored
        self._metrics.lines(LineOutcome.STORED, stored)
        self._metrics.lines(LineOutcome.REPLAYED, replayed)
        self._metrics.lines(LineOutcome.REFUSED, refused)
        self._metrics.lines(LineOutcome.CUT, cut)
        if refused:
            log.warning(
                "Строки встреч, которые не хранятся, отброшены", home=home.value, lines=refused
            )
        return AppendOutcome(stored, replayed, refused)


def _grouped(
    lines: Sequence[LiveLine], facts: dict[UUID, _Facts]
) -> tuple[dict[UUID | None, list[dict[str, Any]]], int, int]:
    """The rows to insert by company, and how many lines were refused and cut."""
    groups: dict[UUID | None, list[dict[str, Any]]] = defaultdict(list)
    refused = cut = 0
    for line in lines:
        fact = facts.get(line.meeting_id)
        text_value, was_cut = fitted_text(line.text)
        if fact is None or not text_value:
            refused += 1
            continue
        cut += was_cut
        groups[fact.org_id].append(
            {
                "session_id": line.meeting_id,
                "seq": line.seq,
                "meeting_started_at": fact.started_at,
                "org_id": fact.org_id,
                "started_at": line.started_at,
                "start_ms": offset_ms(fact.started_at, line.started_at),
                "duration_ms": line.duration_ms,
                "speaker_idx": SIDE_SPEAKER[line.side],
                "text": text_value,
                "origin": LineOrigin.LIVE.value,
            }
        )
    return groups, refused, cut


async def _insert(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Insert the rows, a replayed `(meeting, seq)` ignored; how many were new."""
    if not rows:
        return 0
    inserted = (
        insert(TranscriptLineRecord)
        .values(rows)
        .on_conflict_do_nothing()
        .returning(TranscriptLineRecord.seq)
        .cte("inserted")
    )
    # Новые строки считает сервер: повторы ON CONFLICT в счёт не входят, строки не едут к нам.
    return int(await session.scalar(select(func.count()).select_from(inserted)) or 0)


async def _unsettle(session: AsyncSession, meeting_ids: list[UUID]) -> None:
    """A line came after the end: the meeting is to be settled again."""
    if meeting_ids:
        await session.execute(
            update(MeetingRecord)
            .where(MeetingRecord.id.in_(meeting_ids), MeetingRecord.settled_at.is_not(None))
            .values(settled_at=None)
        )


def stored_line(row: TranscriptLineRecord) -> StoredLine:
    """A stored line as other slices see it."""
    return StoredLine(
        row.seq, row.start_ms, row.duration_ms, row.speaker_idx, row.text, LineOrigin(row.origin)
    )
