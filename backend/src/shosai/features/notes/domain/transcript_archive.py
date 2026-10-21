"""The transcript archive's rules: which months go, where a meeting's lines live, and their form.

A month's partition is archived once the month ended more than 12 months ago (§8.1): its
meetings' lines move to the home's bucket as JSON lines, gzipped, one object per meeting
under `archive/transcripts/`, never under `transient/`, which the bucket expires. A line keeps
every column but the two its meeting already holds (the partition key and the company), so
reads, the export and a copy see exactly what the table held. The digest is the SHA-256 of
the uncompressed lines: the archive is verified against it before the pointer is set (plan
step 20).
"""

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final, Protocol, Self
from uuid import UUID

ARCHIVE_AFTER_MONTHS: Final = 12
ARCHIVE_PREFIX: Final = "archive/transcripts/"
MONTHS_IN_YEAR: Final = 12


class TranscriptLine(Protocol):
    """A transcript line as every reader shows it, from the partition or from the archive."""

    @property
    def seq(self) -> int:
        """The line's number in the meeting."""
        ...

    @property
    def started_at(self) -> datetime:
        """When the phrase started."""
        ...

    @property
    def start_ms(self) -> int:
        """Its offset from the meeting's start."""
        ...

    @property
    def duration_ms(self) -> int:
        """How long it lasted."""
        ...

    @property
    def speaker_idx(self) -> int | None:
        """The voice that said it, when known."""
        ...

    @property
    def text(self) -> str:
        """What was said."""
        ...

    @property
    def origin(self) -> str:
        """`live` or `recording`."""
        ...


@dataclass(frozen=True, slots=True)
class ArchivedLine:
    """One transcript line as the archive keeps it."""

    seq: int
    started_at: datetime
    start_ms: int
    duration_ms: int
    speaker_idx: int | None
    text: str
    origin: str
    run_id: UUID | None
    created_at: datetime

    def encoded(self) -> dict[str, object]:
        """The line as one JSON object, with times and ids as text."""
        return {
            "seq": self.seq, "started_at": self.started_at.isoformat(), "start_ms": self.start_ms,
            "duration_ms": self.duration_ms, "speaker_idx": self.speaker_idx, "text": self.text,
            "origin": self.origin, "run_id": str(self.run_id) if self.run_id else None,
            "created_at": self.created_at.isoformat(),
        }  # fmt: skip

    @classmethod
    def decoded(cls, values: dict[str, object]) -> Self:
        """A line back from its JSON object."""
        run_id = values["run_id"]
        return cls(
            seq=int(str(values["seq"])),
            started_at=datetime.fromisoformat(str(values["started_at"])),
            start_ms=int(str(values["start_ms"])), duration_ms=int(str(values["duration_ms"])),
            speaker_idx=None if values["speaker_idx"] is None else int(str(values["speaker_idx"])),
            text=str(values["text"]), origin=str(values["origin"]),
            run_id=None if run_id is None else UUID(str(run_id)),
            created_at=datetime.fromisoformat(str(values["created_at"])),
        )  # fmt: skip


def archive_key(meeting_id: UUID) -> str:
    """The object a meeting's archived lines live in."""
    return f"{ARCHIVE_PREFIX}{meeting_id}.jsonl.gz"


def last_month_due(now: datetime) -> date:
    """The first day of the newest month whose partition is due: it ended 12 months ago or earlier.

    Partitions are cut on UTC months (`core/db/partitions`), so the months here are UTC's.
    """
    current = now.astimezone(UTC).date().replace(day=1)
    months = current.year * MONTHS_IN_YEAR + current.month - 1 - ARCHIVE_AFTER_MONTHS - 1
    return date(months // MONTHS_IN_YEAR, months % MONTHS_IN_YEAR + 1, 1)


def archive_due(started_at: datetime, now: datetime) -> bool:
    """Whether a meeting's month is due: its partition may already be gone."""
    return started_at.astimezone(UTC).date().replace(day=1) <= last_month_due(now)


def encode_lines(lines: Iterable[ArchivedLine]) -> bytes:
    """The lines as JSON lines in `seq` order, keys sorted: the bytes the digest is taken over."""
    ordered = sorted(lines, key=lambda line: line.seq)
    return b"".join(
        json.dumps(line.encoded(), sort_keys=True, ensure_ascii=False).encode() + b"\n"
        for line in ordered
    )


def decode_lines(data: bytes) -> list[ArchivedLine]:
    """The lines of an archive's uncompressed bytes, in `seq` order."""
    return [ArchivedLine.decoded(json.loads(row)) for row in data.splitlines() if row]


def lines_digest(data: bytes) -> str:
    """The SHA-256 of the uncompressed lines."""
    return hashlib.sha256(data).hexdigest()


def spoken_order(lines: Sequence[ArchivedLine]) -> list[ArchivedLine]:
    """The lines in the order they were spoken, as every reader shows them."""
    return sorted(lines, key=lambda line: (line.start_ms, line.seq))


def page_after(
    lines: Sequence[ArchivedLine], after: tuple[int, int] | None, limit: int
) -> list[ArchivedLine]:
    """Lines past a `(start_ms, seq)` position as spoken, and one more to show a next page."""
    ordered = spoken_order(lines)
    if after is not None:
        ordered = [line for line in ordered if (line.start_ms, line.seq) > after]
    return ordered[: limit + 1]
