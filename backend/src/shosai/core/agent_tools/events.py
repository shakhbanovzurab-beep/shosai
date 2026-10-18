"""The audit event of a Leo action's item, written by the slice that applied it (Leo §8.4).

Each approved item that takes effect writes `agent.action_item.executed` in the effect's
transaction — ids and codes, never content — and the agent turns it into its audit log.
"""

from typing import ClassVar

from shosai.core.events.domain_event import DomainEvent, EventCode


class ActionItemExecuted(DomainEvent):
    """One approved item of a Leo action took effect in its slice; the agent audits it."""

    event_type: ClassVar[str] = "agent.action_item.executed"
    version: ClassVar[int] = 1
    item_key: EventCode
    tool: EventCode
    targets: int
