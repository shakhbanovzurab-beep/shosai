"""A plan's ceiling of people in a call: in the limits, the cache and the admin's contract
(meetings A4, MR-D2)."""

import json
import uuid
from datetime import UTC, datetime

import pytest

from shosai.features.billing.application.entitlement_entries import EntitlementEntry
from shosai.features.billing.contracts import EntitlementSnapshot, EntitlementSource
from shosai.features.billing.domain.plans import Audience, ModelTier, PlanLimits, PlanRuleError
from shosai.features.billing.infrastructure.entitlement_codec import decode, encode


def limits(room_participants: int | None) -> PlanLimits:
    """Limits with only the call's ceiling set."""
    return PlanLimits(
        meeting_minutes_per_month=None,
        file_manager_gb=None,
        knowledge_base_mb=None,
        room_participants=room_participants,
    )


def test_the_ceiling_is_a_limit_like_the_others() -> None:
    assert limits(None).covers(limits(50))
    assert limits(50).covers(limits(10))
    assert not limits(10).covers(limits(50))
    assert not limits(10).covers(limits(None))
    with pytest.raises(PlanRuleError):
        limits(-1)
    assert limits(None).weekly_tokens[ModelTier.FRONTIER] == 0


def entry(room_participants: int | None) -> EntitlementEntry:
    """A cached Free entry with the ceiling."""
    snapshot = EntitlementSnapshot(
        user_id=uuid.uuid4(), plan_slug="free", plan_name="Free", audience=Audience.INDIVIDUAL,
        paid=False, in_grace=False, paid_until=None, limits=limits(room_participants),
        capabilities=frozenset(), source=EntitlementSource.PERSONAL, workspace_id=None, version=3,
    )  # fmt: skip
    return EntitlementEntry(snapshot, None, datetime(2026, 11, 1, tzinfo=UTC), "catalogue-1")


def test_the_cache_keeps_the_ceiling_and_reads_an_entry_written_before_it() -> None:
    assert decode(encode(entry(12))).snapshot.limits.room_participants == 12

    older = json.loads(encode(entry(None)))
    del older["snapshot"]["limits"]["room_participants"]
    assert decode(json.dumps(older).encode()).snapshot.limits.room_participants is None
