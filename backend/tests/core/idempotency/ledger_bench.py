"""A probe effect for the ledger tests: one probe row per run, its id as the outcome."""

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.idempotency.ledger import EffectScope
from tests.core.db.probe_table import probe_records

NOTES = EffectScope("probe.write_note", timedelta(hours=24))


class NoteWritten(BaseModel):
    """The outcome a repeat of the key returns."""

    note_id: UUID


@dataclass
class NoteWriter:
    """Writes one probe row per run in the caller's session and counts its runs."""

    note: str = "note"
    runs: int = 0
    failures: list[Exception] = field(default_factory=list)

    async def write(self, session: AsyncSession) -> NoteWritten:
        """The effect: a probe row, or the next planned failure after writing it."""
        self.runs += 1
        note_id = uuid.uuid7()
        await session.execute(sa.insert(probe_records).values(id=note_id, note=self.note))
        if self.failures:
            raise self.failures.pop(0)
        return NoteWritten(note_id=note_id)
