"""A fact's row as memory's rules see it, and back (memory plan §3.6).

The rules work on `Fact`; a change is written back onto the same row, or a new row for a
successor, in the caller's transaction. A fact the person can see is current or waiting, in a
space they belong to now and not on its way to erasure.
"""

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, or_

from shosai.core.agent_tools.context import Taint
from shosai.features.memory.domain.facts import (
    EndReason,
    Fact,
    FactKind,
    FactStatus,
    MemorySource,
    Sensitivity,
)
from shosai.features.memory.infrastructure.records import MemoryFactRecord

FACT = MemoryFactRecord
TAINTS = {Taint.NONE: "none", Taint.EXTERNAL: "external"}
TAINT_OF = {value: taint for taint, value in TAINTS.items()}


def fact_of(row: MemoryFactRecord) -> Fact:
    """The rules' view of a row."""
    return Fact(
        id=row.id,
        kind=FactKind(row.kind),
        statement=row.statement,
        status=FactStatus(row.status),
        source=MemorySource(row.source_kind),
        created_at=row.created_at,
        last_confirmed_at=row.last_confirmed_at,
        explicit=row.explicit,
        confirmed=row.confirmed,
        pinned=row.pinned,
        sensitivity=Sensitivity(row.sensitivity),
        source_taint=TAINT_OF[row.source_taint],
        confidence=row.confidence,
        confirmations=row.confirmations,
        valid_to=row.valid_to,
        superseded_by=row.superseded_by,
        ended_reason=EndReason(row.ended_reason) if row.ended_reason else None,
        ended_at=row.ended_at,
    )


def write_back(row: MemoryFactRecord, fact: Fact, now: datetime) -> None:
    """The fact's changeable columns onto its row."""
    row.status = fact.status.value
    row.confirmed = fact.confirmed
    row.pinned = fact.pinned
    row.confirmations = fact.confirmations
    row.last_confirmed_at = fact.last_confirmed_at
    row.valid_to = fact.valid_to
    row.superseded_by = fact.superseded_by
    row.ended_reason = fact.ended_reason.value if fact.ended_reason else None
    row.ended_at = fact.ended_at
    row.updated_at = now


def successor_row(old: MemoryFactRecord, fact: Fact, now: datetime) -> MemoryFactRecord:
    """A new row for the fact that takes the old one's place, in the old one's space."""
    return MemoryFactRecord(
        id=fact.id,
        user_id=old.user_id,
        org_id=old.org_id,
        kind=fact.kind.value,
        statement=fact.statement,
        source_kind=fact.source.value,
        source_ref={"replaced": str(old.id)},
        confidence=fact.confidence,
        sensitivity=old.sensitivity,
        explicit=fact.explicit,
        confirmed=fact.confirmed,
        source_taint=TAINTS[fact.source_taint],
        status=fact.status.value,
        pinned=fact.pinned,
        confirmations=fact.confirmations,
        last_confirmed_at=fact.last_confirmed_at,
        valid_from=now,
        created_at=now,
        updated_at=now,
    )


def visible(user_id: UUID, spaces: Collection[UUID]) -> ColumnElement[bool]:
    """The person's current and waiting facts in Personal and the spaces they are in now."""
    return and_(
        FACT.user_id == user_id,
        FACT.status.in_((FactStatus.ACTIVE.value, FactStatus.CANDIDATE.value)),
        FACT.valid_to.is_(None),
        FACT.erase_after.is_(None),
        or_(FACT.org_id.is_(None), FACT.org_id.in_(tuple(spaces))),
    )
