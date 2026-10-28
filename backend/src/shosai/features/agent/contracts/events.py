"""The events agent publishes (agent plan §3.2): ids only, never a word of the conversation.

`agent.turn.completed` tells the slices that work after a turn — memory admits facts from it,
proactive learns the person is active — which turn of which thread ended; each reads what it
needs through its own contract. `agent.skill.removed` tells studio a person uninstalled a
skill, so it leaves the person's prompts (ADR 0068 AG-D11).
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


class SkillRemoved(DomainEvent):
    """A person uninstalled one of their skills; written in the uninstall's transaction."""

    event_type: ClassVar[str] = "agent.skill.removed"
    version: ClassVar[int] = 1
    user_id: UUID
    skill_id: UUID
