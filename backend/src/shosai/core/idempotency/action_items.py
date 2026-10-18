"""A write tool's `execute`: the planned effect once per item key, with its audit event.

The Action Gateway hands each approved item to its slice with the key `<action>:<index>`
(Leo §8.4 rule 2). The slice opens its own transaction under the principal's scope and
calls `ActionItems.once` there: the key is claimed in the effect-key ledger, the effect
runs, and `agent.action_item.executed` (ids and codes, no content) is written to the
outbox — all three commit together or not at all (rule 6). A repeat of the key returns the
stored outcome and writes nothing; an effect that raises aborts the transaction, so a
refused item leaves no key and no event behind.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Final

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope

# Дольше любого повтора элемента: заявка живёт час, поручение — до своего срока и допуска.
ACTION_ITEMS: Final = EffectScope("agent.action_items", keep=timedelta(days=30))


class ActionItems:
    """Applies write tools' items once per key, in the slice's transaction."""

    def __init__(self, effects: EffectLedger, outbox: EventOutbox) -> None:
        self._effects, self._outbox = effects, outbox

    async def once[O: BaseModel](
        self,
        session: AsyncSession,
        item: tuple[str, str, int],
        output: type[O],
        effect: Callable[[], Awaitable[O]],
    ) -> O:
        """Apply the item's effect unless its key was applied; the outcome either way.

        `item` is the key, the tool's name and how many targets the plan froze.
        """
        key, tool, targets = item

        async def audited() -> O:
            outcome = await effect()
            event = ActionItemExecuted(item_key=key, tool=tool, targets=targets)
            await self._outbox.add(session, event)
            return outcome

        applied = await self._effects.once(session, EffectKey(ACTION_ITEMS, key), output, audited)
        return applied.outcome
