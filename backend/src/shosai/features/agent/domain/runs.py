"""A run: one execution of Leo for one input, and the limits it lives within (Leo §5.1, §12).

A run is `running` while a worker of the `agent` queue drives it (ADR 0068 AG-D12), `paused`
while a write waits for the person, and ends exactly once: `completed` (answered, stopped, or
closed after a pause), `failed` with a code, or `cancelled`. No transition leaves an end. The
limits are fixed here: deadlines, the thread lease, the event log, the number of runs a person
may have at once and a worker may drive.
"""

from datetime import timedelta
from enum import StrEnum
from typing import Final

TURN_DEADLINE: Final = timedelta(seconds=180)
BACKGROUND_DEADLINE: Final = timedelta(seconds=300)
# Модель молчит дольше — прогон кончается `model_unavailable`.
STREAM_STALL: Final = timedelta(seconds=45)
READ_TOOL_TIMEOUT: Final = timedelta(seconds=20)
LEASE_TTL: Final = timedelta(seconds=30)
LEASE_RENEWAL: Final = timedelta(seconds=10)
EVENT_LOG_TTL: Final = timedelta(hours=1)
# Журнал прогона на паузе живёт дольше карточки: решение пишет в него исход и конец прогона.
PAUSED_LOG: Final = timedelta(hours=1, minutes=15)
EVENT_LOG_MAX: Final = 2_000
HEARTBEAT: Final = timedelta(seconds=15)
RUNS_PER_PERSON: Final = 2
RUNS_PER_WORKER: Final = 48
# Сколько ждёт ответ на «Одобрить», прежде чем вернуть `executing` и досказать событием.
APPROVAL_WAIT: Final = timedelta(seconds=20)


class RunStatus(StrEnum):
    """Where a run stands."""

    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL: Final = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})


class RunEvent(StrEnum):
    """What happens to a run."""

    PAUSE = "pause"
    RESUME = "resume"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"
    # Пауза закрыта без эпилога: тред ушёл дальше или чекпойнт потерян.
    CLOSE = "close"


_TRANSITIONS: Final[dict[tuple[RunStatus, RunEvent], RunStatus]] = {
    (RunStatus.RUNNING, RunEvent.PAUSE): RunStatus.PAUSED,
    (RunStatus.RUNNING, RunEvent.COMPLETE): RunStatus.COMPLETED,
    (RunStatus.RUNNING, RunEvent.FAIL): RunStatus.FAILED,
    (RunStatus.RUNNING, RunEvent.CANCEL): RunStatus.CANCELLED,
    (RunStatus.PAUSED, RunEvent.RESUME): RunStatus.RUNNING,
    (RunStatus.PAUSED, RunEvent.CLOSE): RunStatus.COMPLETED,
    (RunStatus.PAUSED, RunEvent.CANCEL): RunStatus.CANCELLED,
}


class RunTransitionError(ValueError):
    """The event does not apply to the run in its status."""


def next_status(current: RunStatus, event: RunEvent) -> RunStatus:
    """The status after the event; an ended run accepts nothing."""
    status = _TRANSITIONS.get((current, event))
    if status is None:
        message = f"прогон в статусе {current} не принимает событие {event}"
        raise RunTransitionError(message)
    return status


class RunFailure(StrEnum):
    """Why a run failed; the code the stream's `run.failed` carries and the client words."""

    MODEL_UNAVAILABLE = "model_unavailable"
    # Недельные или дневные токены тарифа кончились посреди прогона.
    LIMIT_REACHED = "token_limit"
    TURN_DEADLINE = "turn_deadline"
    PROCESS_LOST = "process_lost"
    FAILED = "failed"


class CloseReason(StrEnum):
    """Why a paused run closed without its epilogue: its card ended unapproved, its frame was
    gone when the approval came, a new turn took its thread, or its thread was deleted."""

    SUPERSEDED = "superseded"
    CHECKPOINT_LOST = "checkpoint_lost"
    DECIDED = "decided"
    NEW_TURN = "new_turn"


class Channel(StrEnum):
    """Where a run's input came from."""

    WEB = "web"
    ADMIN = "admin"
