"""Events of the AI port (target architecture §12): ids and numbers only."""

from datetime import date
from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent


class UserSpendExceeded(DomainEvent):
    """A user's AI spend today passed the alert threshold; once per user and UTC day (F6-D6).

    F5 turns it into an alert; an operator reads the account card and blocks through
    `identity` if the spend is abuse.
    """

    event_type: ClassVar[str] = "ai.user_spend.exceeded"
    version: ClassVar[int] = 1

    user_id: UUID
    day: date
    spend_micro_usd: int
    threshold_micro_usd: int
