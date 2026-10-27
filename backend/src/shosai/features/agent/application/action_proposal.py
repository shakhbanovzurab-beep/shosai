"""A write the model calls, proposed as a card for the person to decide (Leo §5.3, §8.4).

The write's slice plans it — freezing the exact targets and the data its `execute` reads back,
or refusing with a typed error the model can act on — and previews it for the card. The card's
friction follows AG-D7's rule: a warning, approved on the screen only, when the run read text
someone else wrote or the write cannot be undone, raised by a bound judge (decisions'
`action.friction`) when it asks for more. One transaction stores the action as
`proposed` with its nonce, its hour and the space the change goes to, audits the proposal and
renders its card in the person's language; a preview its slice has no words for is refused,
since no card could show it. Nothing is written to the slice's data until the person approves.
A call that sends data out of a tainted run is proposed the same way, its card worded from
its arguments by its tool's one wording (`egress_calls`).
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.bindings import ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolError, ToolErrorCode
from shosai.core.agent_tools.spec import Reversibility
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.ids import new_id
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_rows import AuditEntry, audit
from shosai.features.agent.application.egress_calls import egress_item
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.action_items import ActionItem, redacted
from shosai.features.agent.domain.actions import (
    NONCE_BYTES,
    ActionStatus,
    AuditEvent,
    ProposalOrigin,
    expires_at,
)
from shosai.features.agent.domain.friction import friction_rule
from shosai.features.agent.infrastructure.run_records import AgentActionRecord

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Proposed:
    """The stored action, its one item and its card."""

    record: AgentActionRecord
    item: ActionItem
    card: dict[str, JsonValue]


class ActionProposer:
    """Turns a model's write call into a stored proposal."""

    def __init__(
        self,
        transactions: HomeTransactions,
        cards: ActionCards,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        judging: FrictionJudging | None = None,
    ) -> None:
        self._transactions = transactions
        self._cards = cards
        self._clock = clock
        self._judging = judging

    async def propose(
        self,
        write: WriteTool[Any, Any],
        arguments: BaseModel,
        context: ToolContext,
        run: tuple[TurnPayload, RunWork],
    ) -> Proposed | ToolError:
        """The stored proposal, or the slice's refusal to plan it."""
        spec = write.spec
        planned = await write.plan(arguments, context)
        if isinstance(planned, ToolError):
            return planned
        preview = await write.preview(planned, context)
        if self._cards.wording(spec.name, preview.key) is None:
            log.error("Превью записи Leo без формулировки", tool=spec.name, key=preview.key)
            return ToolError(ToolErrorCode.FAILED)
        reversibility = spec.reversibility or Reversibility.REVERSIBLE
        item = ActionItem(
            tool=spec.name, targets=planned.targets, plan=dict(planned.data),
            fields=redacted(arguments.model_dump(mode="json")), preview_key=preview.key,
            preview_params=dict(preview.params), reversibility=reversibility.value,
        )  # fmt: skip
        return await self._stored(item, planned.org_id, run)

    async def propose_call(
        self,
        tool: ReadTool[Any, Any],
        arguments: BaseModel,
        call_id: str,
        run: tuple[TurnPayload, RunWork],
    ) -> Proposed | ToolError:
        """The stored proposal of a call that sends data out, worded from its arguments."""
        item = egress_item(tool.spec, arguments, call_id)
        if item is None:
            log.error("Вызов наружу без формулировки карточки", tool=tool.spec.name)
            return ToolError(ToolErrorCode.FAILED)
        return await self._stored(item, None, run)

    async def _stored(
        self, item: ActionItem, org_id: UUID | None, run: tuple[TurnPayload, RunWork]
    ) -> Proposed:
        """The action stored as `proposed`, audited, with its card."""
        payload, work = run
        action_id = new_id()
        if self._judging is None:
            friction = friction_rule(work.taint, Reversibility(item.reversibility))
        else:
            friction = await self._judging.friction(item, org_id, run, action_id)
        now = self._clock()
        record = AgentActionRecord(
            id=action_id, user_id=payload.user_id, org_id=org_id,
            thread_id=payload.thread_id, run_id=payload.run_id, message_id=payload.reply_id,
            origin=ProposalOrigin.TURN.value, origin_key=None,
            status=ActionStatus.PROPOSED.value, nonce=secrets.token_urlsafe(NONCE_BYTES),
            items=[item.stored()],
            friction=int(friction),
            taint=int(work.taint), taint_sources=list(work.taint_sources), not_before=None,
            expires_at=expires_at(now, ProposalOrigin.TURN), created_at=now, updated_at=now,
        )  # fmt: skip
        async with self._transactions.begin(payload.scope()) as session:
            session.add(record)
            await session.flush()
            entry = AuditEntry(AuditEvent.PROPOSED, tool=item.tool, targets=len(item.targets))
            audit(session, record, entry, now)
            (card,) = await self._cards.cards(session, [record])
        return Proposed(record, item, card)
