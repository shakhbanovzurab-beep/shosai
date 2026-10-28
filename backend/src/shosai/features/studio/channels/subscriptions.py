"""Studio's consumer of agent's events: an uninstalled skill leaves the person's prompts.

The delivery's transaction runs in the person's home and scope; one statement takes the skill
off every prompt, and the delivery mark written beside it makes a redelivered event change
nothing more. A prompt keeps its other skills in their order.
"""

from datetime import timedelta
from typing import Any, Final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.contracts.events import SkillRemoved
from shosai.features.studio.infrastructure.prompt_store import detach_skill

DEADLINE: Final = timedelta(seconds=30)
log = structlog.stdlib.get_logger(__name__)


async def skill_removed(session: AsyncSession, received: ReceivedEvent[SkillRemoved]) -> None:
    """Take the uninstalled skill off the person's prompts."""
    event = received.event
    prompts = await detach_skill(session, event.user_id, event.skill_id)
    log.info("Навык снят с промтов", skill_id=str(event.skill_id), prompts=prompts)


SUBSCRIPTIONS: Final[tuple[EventSubscription[Any], ...]] = (
    EventSubscription(
        consumer="studio.skill_detach",
        event=SkillRemoved,
        queue=TaskQueue.DEFAULT,
        deadline=DEADLINE,
        handle=skill_removed,
    ),
)
