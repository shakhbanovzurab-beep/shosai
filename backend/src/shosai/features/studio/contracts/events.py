"""The events studio publishes (studio plan §3.2, ADR 0074): ids and codes only.

`alerting` reports both in the monitoring chat: a model switched off — by the admin, or by
the daily refresh because OpenRouter no longer lists it — and a tier a price proposes, which
changes nothing until the admin confirms it (ST-D4, amended by the owner).
"""

from enum import StrEnum
from typing import ClassVar

from shosai.core.events.domain_event import DomainEvent, EventCode
from shosai.features.studio.domain.roles import Tier


class DisabledBy(StrEnum):
    """Who switched a model off."""

    ADMIN = "admin"
    UPSTREAM = "upstream"


class ModelDisabled(DomainEvent):
    """A catalogue model was switched off; people's choices of it fall to the defaults."""

    event_type: ClassVar[str] = "studio.model.disabled"
    version: ClassVar[int] = 1
    model_id: EventCode
    reason: DisabledBy


class ModelTierProposed(DomainEvent):
    """A model's price proposes another tier; its confirmed tier stays until the admin acts."""

    event_type: ClassVar[str] = "studio.model.tier_proposed"
    version: ClassVar[int] = 1
    model_id: EventCode
    confirmed: Tier
    proposed: Tier


STUDIO_EVENTS: tuple[type[DomainEvent], ...] = (ModelDisabled, ModelTierProposed)
