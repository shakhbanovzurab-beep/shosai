"""A broadcast's states, who its link admits and what each part may do (MR-D7)."""

from dataclasses import replace

import pytest

from shosai.features.meetings.domain.broadcasts import (
    AUDIENCE,
    OFF_AIR,
    ON_STAGE,
    SPEAKERS_MAX,
    VIEWERS_MAX,
    BroadcastEntry,
    BroadcastState,
    EntryFacts,
    StageRole,
    chat_burst,
    entry,
    grants_for,
    may_manage_cohosts,
    may_moderate,
    may_move,
    stage_has_room,
)

LIVE_VIEWER = EntryFacts(state=BroadcastState.LIVE, role=None, waiting_room=False, viewers=10)


@pytest.mark.parametrize(
    ("current", "allowed"),
    [
        (BroadcastState.SCHEDULED, {BroadcastState.LIVE, BroadcastState.ENDED}),
        (BroadcastState.LIVE, {BroadcastState.ENDED}),
        (BroadcastState.ENDED, set()),
    ],
)
def test_every_state_has_its_exits(current: BroadcastState, allowed: set[BroadcastState]) -> None:
    assert {target for target in BroadcastState if may_move(current, target)} == allowed


@pytest.mark.parametrize(
    ("facts", "answer"),
    [
        (LIVE_VIEWER, BroadcastEntry.AUDIENCE),
        (replace(LIVE_VIEWER, waiting_room=True), BroadcastEntry.WAIT),
        (replace(LIVE_VIEWER, viewers=VIEWERS_MAX), BroadcastEntry.FULL),
        (replace(LIVE_VIEWER, state=BroadcastState.SCHEDULED), BroadcastEntry.NOT_LIVE),
        # Сцена собирается до эфира и входит при полном зале, но не после конца.
        (
            replace(LIVE_VIEWER, state=BroadcastState.SCHEDULED, role=StageRole.SPEAKER),
            BroadcastEntry.STAGE,
        ),
        (replace(LIVE_VIEWER, role=StageRole.COHOST, viewers=VIEWERS_MAX), BroadcastEntry.STAGE),
        (
            replace(LIVE_VIEWER, state=BroadcastState.ENDED, role=StageRole.HOST),
            BroadcastEntry.ENDED,
        ),
    ],
)
def test_the_link_answers_by_state_and_part(facts: EntryFacts, answer: BroadcastEntry) -> None:
    assert entry(facts) is answer


def test_the_stage_speaks_and_the_audience_only_watches_hidden() -> None:
    assert grants_for(StageRole.HOST) is ON_STAGE
    assert grants_for(StageRole.SPEAKER, on_air=False) is OFF_AIR
    assert grants_for(None) is AUDIENCE
    assert not AUDIENCE.can_publish
    assert not AUDIENCE.can_publish_data
    assert AUDIENCE.hidden
    assert not OFF_AIR.can_publish
    assert OFF_AIR.can_publish_data


def test_moderation_belongs_to_the_hosts_and_cohosts_to_the_host_only() -> None:
    assert may_moderate(StageRole.HOST)
    assert may_moderate(StageRole.COHOST)
    assert not may_moderate(StageRole.SPEAKER)
    assert not may_moderate(None)
    assert may_manage_cohosts(StageRole.HOST)
    assert not may_manage_cohosts(StageRole.COHOST)


def test_the_audience_chats_slower_and_the_stage_holds_ten_speakers() -> None:
    assert chat_burst(None) < chat_burst(StageRole.SPEAKER)
    assert stage_has_room(SPEAKERS_MAX - 1)
    assert not stage_has_room(SPEAKERS_MAX)
