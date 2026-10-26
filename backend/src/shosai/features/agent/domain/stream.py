"""The events a run streams, and the rules of their order (ADR 0032, agent plan §3.3).

Every event carries the next number of its run, so a client resumes after the last it saw
and never sees one twice. A run ends with exactly one terminal event — `run.completed` or
`run.failed` — after which it streams nothing; `run.paused` is not an end, since an approval
resumes the same run, but it ends a follower's stream when nothing follows it yet. A step
opens once and closes once, with the activity it showed; the activity is a tool's name or one
of the reasoning codes, and the cabinet words it, falling back to a generic line for one it
does not know.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final

from pydantic import JsonValue

type EventData = Mapping[str, JsonValue]


class EventKind(StrEnum):
    """The closed vocabulary of the stream; clients ignore a kind they do not know."""

    RUN_STARTED = "run.started"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    TEXT_DELTA = "text.delta"
    SOURCES = "sources"
    ARTIFACT = "artifact"
    CLIENT_ACTION = "client.action"
    ACTION_PROPOSED = "action.proposed"
    ACTION_UPDATED = "action.updated"
    RUN_PAUSED = "run.paused"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


TERMINAL: Final = frozenset({EventKind.RUN_COMPLETED, EventKind.RUN_FAILED})


def closes_stream(event: StreamEvent, *, followed: bool) -> bool:
    """Whether a follower stops at the event: at the run's end, or at a pause nothing follows
    yet — the approval's events come later, on the same run, to a new follower."""
    if event.kind in TERMINAL:
        return True
    return event.kind is EventKind.RUN_PAUSED and not followed


_STEP_ENDS: Final = frozenset({EventKind.STEP_COMPLETED, EventKind.STEP_FAILED})


class Activity(StrEnum):
    """What a step that is not a tool call shows."""

    THINK = "think"
    WRITE_ANSWER = "write_answer"
    READ_ATTACHMENT = "read_attachment"


class Completion(StrEnum):
    """How a completed run ended (`run.completed.outcome`)."""

    ANSWERED = "answered"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """One event of a run: its number, kind and payload."""

    seq: int
    kind: EventKind
    data: EventData


class StreamClosedError(ValueError):
    """An event after the run's end, or a step closed that never opened."""


@dataclass(frozen=True, slots=True)
class StreamLedger:
    """What a run has streamed: the last number, its open steps, and whether it ended."""

    seq: int = 0
    open_steps: frozenset[str] = field(default_factory=frozenset)
    ended: bool = False

    def emit(self, kind: EventKind, data: EventData) -> tuple[StreamLedger, StreamEvent]:
        """The next event; refused after the end, or for a step out of order."""
        if self.ended:
            message = "прогон уже закончился: событий после конца нет"
            raise StreamClosedError(message)
        steps = self.open_steps
        if kind is EventKind.STEP_STARTED or kind in _STEP_ENDS:
            steps = _steps_after(steps, kind, data)
        event = StreamEvent(self.seq + 1, kind, data)
        # Конец прогона закрывает и незакрытые шаги: клиент показывает их остановленными.
        if kind in TERMINAL:
            steps = frozenset()
        ledger = replace(self, seq=event.seq, open_steps=steps, ended=kind in TERMINAL)
        return ledger, event


def _steps_after(steps: frozenset[str], kind: EventKind, data: EventData) -> frozenset[str]:
    step = data.get("id")
    if not isinstance(step, str) or not step:
        message = "у события шага есть строковый id"
        raise StreamClosedError(message)
    if kind is EventKind.STEP_STARTED:
        if step in steps:
            message = f"шаг {step} уже открыт"
            raise StreamClosedError(message)
        return steps | {step}
    if step not in steps:
        message = f"шаг {step} не открыт"
        raise StreamClosedError(message)
    return steps - {step}
