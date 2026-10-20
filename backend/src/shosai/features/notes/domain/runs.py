"""A post-meeting run and its stages (§8.1 Pipeline run, §10, §14 rule 6; plan §3.4).

A run is the work one source asks for — the live meeting's end, an import, a desktop
recording, a rewrite of the notes — as a sequence of stages. A stage runs, then is done, is
given back for another attempt after a pause, or fails for good: after three attempts on
any path, or at once for a failure retrying cannot help (the draft retried empty
recognition three times and paid each time, 30a31cc12). A finished stage is never run
again. A run fails when a critical stage fails, is partially completed when only a
non-critical one did, and never leaves a terminal state.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

MAX_ATTEMPTS: Final = 3
# Пауза перед второй и третьей попыткой: мгновенный повтор черновика сжигал все попытки
# за секунду (a70ee46e1).
BACKOFF: Final = (timedelta(seconds=5), timedelta(seconds=30), timedelta(seconds=120))
EFFECT_KEY_MAX: Final = 200


class RunSource(StrEnum):
    """What asked for the run."""

    LIVE = "live"
    IMPORT = "import"
    RECORDING = "recording"
    REGENERATE = "regenerate"


class RunState(StrEnum):
    """A run's state as §10 names it."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class Stage(StrEnum):
    """One stage of a run."""

    INTAKE = "intake"
    TRANSCRIBE = "transcribe"
    DIARIZE = "diarize"
    ALIGN = "align"
    FINDINGS = "findings"
    WRITE_UP = "write_up"


class StageStatus(StrEnum):
    """Where a stage stands."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


STAGES: Final[Mapping[RunSource, tuple[Stage, ...]]] = {
    RunSource.LIVE: (Stage.FINDINGS, Stage.WRITE_UP),
    RunSource.IMPORT: (
        Stage.INTAKE, Stage.TRANSCRIBE, Stage.DIARIZE, Stage.ALIGN, Stage.FINDINGS, Stage.WRITE_UP,
    ),
    RunSource.RECORDING: (
        Stage.INTAKE, Stage.TRANSCRIBE, Stage.DIARIZE, Stage.ALIGN, Stage.FINDINGS, Stage.WRITE_UP,
    ),
    RunSource.REGENERATE: (Stage.WRITE_UP,),
}  # fmt: skip
# Без разметки говорящих расшифровка остаётся; без остального заметок нет.
NON_CRITICAL: Final = frozenset({Stage.DIARIZE})
# Отказы, которые повтор не исправит.
NEVER_RETRIED: Final = frozenset(
    {
        "transcript_empty",
        "meeting_gone",
        "consent_required",
        "content_refused",
        "upload_exceeds_minutes",
        "recording_too_long",
        "unsupported_audio_format",
        "media_unreadable",
        "attempts_exhausted",
    }
)
TERMINAL: Final = frozenset({RunState.SUCCEEDED, RunState.PARTIALLY_COMPLETED, RunState.FAILED})
RUN_MOVES: Final = {
    RunState.PENDING: frozenset({RunState.RUNNING, RunState.FAILED}),
    RunState.RUNNING: TERMINAL,
    **{state: frozenset[RunState]() for state in TERMINAL},
}
STAGE_MOVES: Final = {
    StageStatus.PENDING: frozenset({StageStatus.RUNNING}),
    # Из работы — готово, провал или назад в очередь за новой попыткой.
    StageStatus.RUNNING: frozenset({StageStatus.DONE, StageStatus.FAILED, StageStatus.PENDING}),
    StageStatus.DONE: frozenset[StageStatus](),
    StageStatus.FAILED: frozenset[StageStatus](),
}


def can_move_run(state: RunState, to: RunState) -> bool:
    """Whether a run in `state` may become `to`."""
    return to in RUN_MOVES[state]


def can_move_stage(status: StageStatus, to: StageStatus) -> bool:
    """Whether a stage in `status` may become `to`."""
    return to in STAGE_MOVES[status]


@dataclass(frozen=True, slots=True)
class StageRecord:
    """A stage's status, the attempts made so far and the code of its last failure."""

    status: StageStatus = StageStatus.PENDING
    attempts: int = 0
    error_code: str | None = None


type Progress = Mapping[Stage, StageRecord]


def initial_progress(source: RunSource) -> dict[Stage, StageRecord]:
    """Every stage of the source, none attempted."""
    return {stage: StageRecord() for stage in STAGES[source]}


def next_stage(source: RunSource, progress: Progress) -> Stage | None:
    """The stage to run now, or None when the run is over."""
    for stage in STAGES[source]:
        record = progress.get(stage, StageRecord())
        if record.status is StageStatus.DONE:
            continue
        if record.status is StageStatus.FAILED:
            if stage in NON_CRITICAL:
                continue
            return None
        return stage
    return None


class Claim(StrEnum):
    """What a delivery of a stage's task does with the stage it finds."""

    RUN = "run"
    # Уже сделана или уже провалена: доставка — повтор, работы нет.
    FINISHED = "finished"
    # Идёт у другого воркера, и его аренда ещё не кончилась.
    HELD = "held"
    # Три попытки истрачены (воркер умирал посреди стадии): стадия проваливается.
    EXHAUSTED = "exhausted"


def claim(record: StageRecord, *, stale: bool) -> Claim:
    """Whether a delivery runs the stage now: a stage runs at most three times on any path.

    `stale` says the stage has been running longer than a worker may hold it, so its worker
    is gone and the stage may be taken over; that take-over is one more attempt.
    """
    if record.status in {StageStatus.DONE, StageStatus.FAILED}:
        return Claim.FINISHED
    if record.status is StageStatus.RUNNING and not stale:
        return Claim.HELD
    if record.attempts >= MAX_ATTEMPTS:
        return Claim.EXHAUSTED
    return Claim.RUN


@dataclass(frozen=True, slots=True)
class Retry:
    """The stage goes back to the queue after `after`."""

    after: timedelta


@dataclass(frozen=True, slots=True)
class GiveUp:
    """The stage failed for good with `code`."""

    code: str


def after_failure(attempts: int, code: str) -> Retry | GiveUp:
    """What follows a failed attempt, `attempts` counting the one that just failed."""
    if attempts < 1:
        message = "неудача — после хотя бы одной попытки"
        raise ValueError(message)
    if code in NEVER_RETRIED or attempts >= MAX_ATTEMPTS:
        return GiveUp(code)
    return Retry(BACKOFF[attempts - 1])


def outcome(source: RunSource, progress: Progress) -> RunState | None:
    """The run's terminal state once every stage has finished, else None."""
    failed = [
        s for s in STAGES[source] if progress.get(s, StageRecord()).status is StageStatus.FAILED
    ]
    if any(stage not in NON_CRITICAL for stage in failed):
        return RunState.FAILED
    if next_stage(source, progress) is not None:
        return None
    return RunState.PARTIALLY_COMPLETED if failed else RunState.SUCCEEDED


def idempotency_key(
    source: RunSource, *, upload_id: UUID | None = None, request_key: str | None = None
) -> str:
    """The key that makes a repeated request answer the same run of a meeting.

    The client's end and the silence sweep share `live`: a meeting has one live run.
    """
    if source is RunSource.IMPORT:
        if upload_id is None:
            message = "импорт узнаётся по своей загрузке"
            raise ValueError(message)
        return f"import:{upload_id}"
    if source is RunSource.REGENERATE:
        if not request_key:
            message = "переписывание узнаётся по ключу запроса"
            raise ValueError(message)
        return f"regenerate:{request_key}"[:EFFECT_KEY_MAX]
    return source.value


def effect_key(run_id: UUID, stage: Stage, part: int = 0) -> str:
    """The provider call's effect key: one cost row per call whatever the retries (inv-9)."""
    if part < 0:
        message = "номер части — от нуля"
        raise ValueError(message)
    return f"notes:{run_id}:{stage.value}:{part}"
