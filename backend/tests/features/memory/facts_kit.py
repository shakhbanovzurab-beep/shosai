"""Facts for memory's tests: one builder, sensible defaults, any field overridden."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import TypedDict, Unpack
from uuid import UUID, uuid4

from hypothesis import strategies as st

from shosai.core.agent_tools.context import Taint
from shosai.features.memory.domain.facts import (
    EndReason,
    Fact,
    FactKind,
    FactStatus,
    Sensitivity,
    SourceKind,
)

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


class FactChanges(TypedDict, total=False):
    """The fields of a fact a test may set."""

    id: UUID
    kind: FactKind
    statement: str
    status: FactStatus
    source: SourceKind
    created_at: datetime
    last_confirmed_at: datetime
    explicit: bool
    confirmed: bool
    pinned: bool
    sensitivity: Sensitivity
    source_taint: Taint
    confidence: float
    confirmations: int
    valid_to: datetime | None
    superseded_by: UUID | None
    ended_reason: EndReason | None
    ended_at: datetime | None


def fact(fact_id: UUID | None = None, **changes: Unpack[FactChanges]) -> Fact:
    """An active fact the person said in a conversation, created and confirmed at `NOW`."""
    base = Fact(
        id=fact_id or uuid4(),
        kind=FactKind.FACT,
        statement="Leads product at Lumen",
        status=FactStatus.ACTIVE,
        source=SourceKind.USER_STATEMENT,
        created_at=NOW,
        last_confirmed_at=NOW,
    )
    return replace(base, **changes)


kinds = st.sampled_from(FactKind)
sources = st.sampled_from(SourceKind)
statuses = st.sampled_from(FactStatus)
