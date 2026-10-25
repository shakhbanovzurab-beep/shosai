"""A slice's write put into a person's thread as a card, without a model round (AG-R2; step 9b2).

The calling slice names a write tool and its arguments for the person, as the person: the
arguments pass the tool's own schema, its slice plans the write and previews it exactly as for
a model's call, with no untrusted text read before it — so the card is the one a turn would
show, decided, expired, executed once and audited like any other. A refusal is the tool's
error code. One transaction stores the action under the caller's `origin_key` — the same key
again returns the same card — adds it to the answer it belongs to, and renders the card in the
language the caller asks for.
"""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.arguments import parse_arguments
from shosai.core.agent_tools.bindings import WriteTool
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.agent_tools.context import Taint, ToolContext
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolError, ToolErrorCode
from shosai.core.agent_tools.spec import Reversibility
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.ids import new_id
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_rows import AuditEntry, audit
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.contracts import ProposalCard, ProposalRefusedError, ProposalRequest
from shosai.features.agent.domain.action_items import ActionItem, redacted
from shosai.features.agent.domain.actions import (
    NONCE_BYTES,
    ActionStatus,
    AuditEvent,
    ProposalOrigin,
    PublicStatus,
    expires_at,
)
from shosai.features.agent.domain.friction import friction_rule
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord

ACTION = AgentActionRecord
MESSAGE = AgentMessageRecord


def card_model(card: dict[str, Any], origin: ProposalOrigin) -> ProposalCard:
    """The rendered card as the contract's shape."""
    preview = card["preview"]
    return ProposalCard(
        id=card["id"], tool=card["tool"], title=card["title"], space=card["space"],
        origin=origin, reversibility=Reversibility(card["reversibility"]),
        warning=card["warning"], taint=card["taint"],
        fields=tuple((row["label"], row["value"]) for row in preview["fields"]),
        body=preview["body"], status=PublicStatus(card["status"]), outcome=card["outcome"],
        nonce=card["nonce"], created_at=datetime.fromisoformat(card["created_at"]),
        expires_at=datetime.fromisoformat(card["expires_at"]),
        resolved_at=None if card["resolved_at"] is None
        else datetime.fromisoformat(card["resolved_at"]),
    )  # fmt: skip


class PortProposals:
    """Binds `ActionProposals`: plans a slice's write and stores it as the person's card."""

    def __init__(
        self,
        transactions: HomeTransactions,
        parts: tuple[AgentToolCatalog, ActionCards, Threads],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._catalog, self._cards, self._threads = parts
        self._clock = clock

    async def propose(self, request: ProposalRequest) -> ProposalCard:
        """The stored card; the same `origin_key` again returns the same card."""
        write = self._catalog.tool(request.tool)
        if not isinstance(write, WriteTool):
            raise ProposalRefusedError(ToolErrorCode.NOT_FOUND.value)
        planned, preview = await self._planned(write, request)
        async with self._transactions.begin(request.scope) as session:
            record = await self._stored(session, request, (write, planned, preview))
            (card,) = await self._cards.cards(session, [record], request.language)
        return card_model(card, request.origin)

    async def _planned(
        self, write: WriteTool[Any, Any], request: ProposalRequest
    ) -> tuple[PlannedEffect, Preview]:
        arguments = parse_arguments(write.spec, request.arguments)
        if isinstance(arguments, ToolError):
            raise ProposalRefusedError(arguments.code.value)
        deadline = self._clock() + write.spec.timeout
        context = ToolContext(request.scope, new_id(), deadline, Taint.NONE)
        planned = await write.plan(arguments, context)
        if isinstance(planned, ToolError):
            raise ProposalRefusedError(planned.code.value)
        preview = await write.preview(planned, context)
        if self._cards.wording(write.spec.name, preview.key) is None:
            raise ProposalRefusedError(ToolErrorCode.FAILED.value)
        return planned, preview

    async def _stored(
        self,
        session: AsyncSession,
        request: ProposalRequest,
        prepared: tuple[WriteTool[Any, Any], PlannedEffect, Preview],
    ) -> AgentActionRecord:
        """The action of the key: stored now with its audit and its answer's mark, or found."""
        write, planned, preview = prepared
        user_id = request.scope.user_id
        if user_id is None:
            message = "предложение — от имени человека"
            raise ValueError(message)
        await self._threads.visible_thread(session, user_id, request.thread_id)
        spec, now = write.spec, self._clock()
        reversibility = spec.reversibility or Reversibility.REVERSIBLE
        item = ActionItem(
            tool=spec.name, targets=planned.targets, plan=dict(planned.data),
            fields=redacted(dict(request.arguments)), preview_key=preview.key,
            preview_params=dict(preview.params), reversibility=reversibility.value,
        )  # fmt: skip
        values: dict[str, Any] = {
            "id": new_id(), "user_id": user_id, "org_id": planned.org_id,
            "thread_id": request.thread_id, "run_id": None, "message_id": request.message_id,
            "origin": request.origin.value, "origin_key": request.origin_key,
            "status": ActionStatus.PROPOSED.value, "nonce": secrets.token_urlsafe(NONCE_BYTES),
            "items": [item.stored()],
            "friction": int(friction_rule(Taint.NONE, reversibility)), "taint": 0,
            "taint_sources": [], "expires_at": expires_at(now, request.origin),
            "created_at": now, "updated_at": now,
        }  # fmt: skip
        made = await session.scalar(
            insert(ACTION).values(**values).on_conflict_do_nothing().returning(ACTION.id)
        )
        record = await session.scalar(
            select(ACTION).where(
                ACTION.user_id == user_id,
                ACTION.origin == request.origin.value,
                ACTION.origin_key == request.origin_key,
            )
        )
        if record is None:
            message = "предложение с ключом источника не записалось и не нашлось"
            raise LookupError(message)
        if made is not None:
            entry = AuditEntry(AuditEvent.PROPOSED, tool=spec.name, targets=len(item.targets))
            audit(session, record, entry, now)
            await session.execute(
                update(MESSAGE)
                .where(MESSAGE.id == request.message_id, MESSAGE.thread_id == request.thread_id)
                .values(action_ids=func.array_append(MESSAGE.action_ids, record.id))
            )
        return record
