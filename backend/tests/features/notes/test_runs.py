"""A run's stages, retries and outcome (notes plan step 1; §14 rule 6)."""

import uuid
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.notes.domain.runs import (
    BACKOFF,
    MAX_ATTEMPTS,
    NEVER_RETRIED,
    RUN_MOVES,
    STAGE_MOVES,
    STAGES,
    TERMINAL,
    GiveUp,
    Retry,
    RunSource,
    RunState,
    Stage,
    StageRecord,
    StageStatus,
    after_failure,
    can_move_run,
    can_move_stage,
    effect_key,
    idempotency_key,
    initial_progress,
    next_stage,
    outcome,
)

sources = st.sampled_from(list(RunSource))
statuses = st.sampled_from([StageStatus.PENDING, StageStatus.DONE, StageStatus.FAILED])


@st.composite
def progresses(draw: st.DrawFn) -> tuple[RunSource, dict[Stage, StageRecord]]:
    source = draw(sources)
    return source, {stage: StageRecord(draw(statuses)) for stage in STAGES[source]}


def test_every_state_has_a_tested_exit_and_terminal_states_never_resurrect() -> None:
    assert can_move_run(RunState.PENDING, RunState.RUNNING)
    assert all(can_move_run(RunState.RUNNING, state) for state in TERMINAL)
    for state in TERMINAL:
        assert not RUN_MOVES[state]
        assert not any(can_move_run(state, to) for to in RunState)
    assert set(RUN_MOVES) == set(RunState)
    assert can_move_stage(StageStatus.RUNNING, StageStatus.PENDING)
    assert not STAGE_MOVES[StageStatus.DONE]
    assert not STAGE_MOVES[StageStatus.FAILED]
    assert set(STAGE_MOVES) == set(StageStatus)


@given(code=st.sampled_from(sorted(NEVER_RETRIED)), attempts=st.integers(1, 10))
def test_a_never_retried_code_is_never_retried(code: str, attempts: int) -> None:
    assert after_failure(attempts, code) == GiveUp(code)


@given(attempts=st.integers(1, 20), code=st.sampled_from(["provider_error", "deadline_exceeded"]))
def test_a_stage_gets_three_attempts_with_growing_pauses(attempts: int, code: str) -> None:
    decision = after_failure(attempts, code)

    if attempts >= MAX_ATTEMPTS:
        assert decision == GiveUp(code)
    else:
        assert decision == Retry(BACKOFF[attempts - 1])
    assert all(earlier < later for earlier, later in pairwise(BACKOFF))


def test_a_failure_comes_after_an_attempt() -> None:
    with pytest.raises(ValueError, match="попытки"):
        after_failure(0, "provider_error")


@given(state=progresses())
def test_the_outcome_follows_the_stages(
    state: tuple[RunSource, dict[Stage, StageRecord]],
) -> None:
    source, progress = state
    failed = {s for s, r in progress.items() if r.status is StageStatus.FAILED}
    result = outcome(source, progress)

    if failed:
        assert result is RunState.FAILED
    elif any(r.status is StageStatus.PENDING for r in progress.values()):
        stage = next_stage(source, progress)
        assert result is None
        assert stage is not None
        assert progress[stage].status is StageStatus.PENDING
    else:
        assert result is RunState.SUCCEEDED


@given(source=sources)
def test_a_new_run_starts_at_its_first_stage_and_skips_finished_ones(source: RunSource) -> None:
    progress = initial_progress(source)
    order: list[Stage] = []
    while (stage := next_stage(source, progress)) is not None:
        order.append(stage)
        progress[stage] = StageRecord(StageStatus.DONE, attempts=1)

    assert tuple(order) == STAGES[source]
    assert outcome(source, progress) is RunState.SUCCEEDED


def test_a_recording_s_speakers_come_with_its_text_and_any_failure_fails_the_run() -> None:
    progress = initial_progress(RunSource.IMPORT)
    for stage in STAGES[RunSource.IMPORT]:
        progress[stage] = StageRecord(
            StageStatus.FAILED if stage is Stage.ALIGN else StageStatus.DONE, attempts=1
        )

    assert STAGES[RunSource.IMPORT] == STAGES[RunSource.RECORDING] == (
        Stage.INTAKE, Stage.TRANSCRIBE, Stage.ALIGN, Stage.FINDINGS, Stage.WRITE_UP,
    )  # fmt: skip
    assert outcome(RunSource.IMPORT, progress) is RunState.FAILED


def test_one_live_run_per_meeting_and_keys_for_the_rest() -> None:
    upload = uuid.uuid4()

    assert idempotency_key(RunSource.LIVE) == "live"
    assert idempotency_key(RunSource.IMPORT, upload_id=upload) == f"import:{upload}"
    assert idempotency_key(RunSource.RECORDING) == "recording"
    assert idempotency_key(RunSource.REGENERATE, request_key="k1") == "regenerate:k1"
    with pytest.raises(ValueError, match="загрузке"):
        idempotency_key(RunSource.IMPORT)
    with pytest.raises(ValueError, match="ключу"):
        idempotency_key(RunSource.REGENERATE)


@given(run_id=st.uuids(), stage=st.sampled_from(list(Stage)), part=st.integers(0, 10_000))
def test_an_effect_key_names_the_run_stage_and_part(
    run_id: uuid.UUID, stage: Stage, part: int
) -> None:
    key = effect_key(run_id, stage, part)

    assert key == f"notes:{run_id}:{stage.value}:{part}"
    assert len(key) <= 200
