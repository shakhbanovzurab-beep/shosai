"""One evaluated turn gathered from what it left: its stream, its model calls, its tool calls
(AG-D8).

The stream is read as the cabinet reads it: the events in order, the answer's text from its
deltas, the last list of sources, the pages the cabinet was sent to, and the end — answered,
stopped, or the failure's code.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import JsonValue

from shosai.features.agent.application.eval_model import RecordingModel
from shosai.features.agent.domain.budgets import Segment
from shosai.features.agent.domain.eval_checks import PAUSED, Card, Observed, ToolRun
from shosai.features.agent.domain.stream import EventKind, StreamEvent

FAILED: Final = "failed"


def observed_turn(
    events: Sequence[StreamEvent],
    recording: RecordingModel,
    calls: tuple[tuple[ToolRun, ...], tuple[ToolRun, ...]],
    context: tuple[Mapping[Segment, int], str, str],
) -> Observed:
    """The turn as it was seen from outside: `calls` holds the calls that ran and the writes
    proposed, `context` its first call's segments, head and tools."""
    runs, proposed = calls
    segments, head, tools_schema = context
    return Observed(
        attempted=tuple(recording.attempted),
        runs=runs,
        events=tuple(event.kind.value for event in events),
        outcome=outcome_of(events),
        answer="".join(text_in(e.data, "text") for e in of_kind(events, EventKind.TEXT_DELTA)),
        sources=sources_of(events),
        navigations=tuple(
            target for event in of_kind(events, EventKind.CLIENT_ACTION) if (target := to_of(event))
        ),
        calls=tuple(recording.calls),
        segments=dict(segments),
        head=head,
        tools_schema=tools_schema,
        cards=tuple(card_of(event) for event in of_kind(events, EventKind.ACTION_PROPOSED)),
        proposed=proposed,
    )


def card_of(event: StreamEvent) -> Card:
    """A proposed card as the stream showed it."""
    action = event.data.get("action")
    action = action if isinstance(action, dict) else {}
    taint = action.get("taint")
    return Card(
        str(action.get("tool")),
        action.get("warning") is True,
        taint if isinstance(taint, str) else None,
    )


def of_kind(events: Sequence[StreamEvent], kind: EventKind) -> list[StreamEvent]:
    """The events of one kind, in order."""
    return [event for event in events if event.kind is kind]


def sources_of(events: Sequence[StreamEvent]) -> int:
    """How many sources the last list named."""
    listed = [event.data.get("sources") for event in of_kind(events, EventKind.SOURCES)]
    return len(listed[-1]) if listed and isinstance(listed[-1], list) else 0


def to_of(event: StreamEvent) -> str:
    """Where a cabinet action sends the person, empty for any other action."""
    navigate = event.data.get("navigate")
    return text_in(navigate, "to") if isinstance(navigate, dict) else ""


def outcome_of(events: Sequence[StreamEvent]) -> str | None:
    """How the run ended: answered or stopped, paused on its card, the failure's code, or None
    while it runs."""
    for event in reversed(events):
        if event.kind is EventKind.RUN_PAUSED:
            return PAUSED
        if event.kind is EventKind.RUN_COMPLETED:
            return text_in(event.data, "outcome")
        if event.kind is EventKind.RUN_FAILED:
            return text_in(event.data, "code") or FAILED
    return None


def text_in(data: Mapping[str, JsonValue], key: str) -> str:
    """A string field of an event, empty when absent."""
    value = data.get(key)
    return value if isinstance(value, str) else ""
