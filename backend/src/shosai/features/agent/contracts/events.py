"""The events agent publishes (agent plan §3.2): ids only, never a word of the conversation.

`agent.turn.completed` tells the slices that work after a turn — memory admits facts from it,
proactive learns the person is active — which turn of which thread ended; each reads what it
needs through its own contract.
"""

from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent


class TurnCompleted(DomainEvent):
    """A turn of a person's thread ended with an answer."""

    event_type: ClassVar[str] = "agent.turn.completed"
    version: ClassVar[int] = 1
    thread_id: UUID
    run_id: UUID
    user_id: UUID
