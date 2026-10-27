"""A voice tool call's events, told to the conversation's socket (ADR 0070, LV-D2).

A text turn writes its events to the run's log for the cabinet's stream; a voice exchange
has a socket instead. The round of tools is the same, so it emits the same events: the steps
reach the socket by their activity and status, a card by its action id; sources and artifacts
stay in the exchange's record, which the thread shows when voice mode closes.
"""

from uuid import UUID

import structlog

from shosai.features.agent.contracts.voice import VoiceEvents
from shosai.features.agent.domain.stream import EventData, EventKind, StreamEvent, StreamLedger

log = structlog.stdlib.get_logger(__name__)

STEP_STATUSES = {EventKind.STEP_COMPLETED: "done", EventKind.STEP_FAILED: "failed"}


class VoiceEmitter:
    """One call's events for the socket, numbered as a run's would be."""

    def __init__(self, events: VoiceEvents) -> None:
        self._events = events
        self._ledger = StreamLedger()
        self._activities: dict[str, str] = {}

    async def emit(self, kind: EventKind, data: EventData) -> StreamEvent:
        """Number the event and tell the socket what it shows."""
        self._ledger, event = self._ledger.emit(kind, data)
        step = str(data.get("id", ""))
        if kind is EventKind.STEP_STARTED:
            activity = str(data.get("activity", ""))
            self._activities[step] = activity
            await self._events.step(activity, "running")
        elif kind in STEP_STATUSES:
            await self._events.step(self._activities.pop(step, ""), STEP_STATUSES[kind])
        elif kind is EventKind.ACTION_PROPOSED:
            await self._proposed(data)
        return event

    async def _proposed(self, data: EventData) -> None:
        card = data.get("action")
        action_id = card.get("id") if isinstance(card, dict) else None
        if not isinstance(action_id, str):
            log.error("Карточка голосового обмена без id", keys=sorted(data))
            return
        await self._events.proposed(UUID(action_id))
