"""The person's decisions on Leo's cards: `/v1/agent/actions/{id}/approve|reject` (step 9a).

Both take the nonce the card showed. `approve` answers within 20 s with the action's end, or
`executing` when it takes longer — the end follows as `action.updated` on the run's stream —
with the run to follow when there is one. Errors use the platform's envelope:
`action_not_found` (404: no card of the person by that id) and `action_not_pending` (409: the
card no longer waits, or it is not the one the person saw). Step 9b adds the card's words —
title, space, fields — and the inbox's `GET /v1/agent/actions*`.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_cards import action_card
from shosai.features.agent.application.action_decisions import ActionDecisions, Decided
from shosai.features.agent.channels.http.shapes import Out, Strict
from shosai.features.agent.domain.actions import NONCE_BYTES, PublicStatus
from shosai.features.identity.contracts import Principal, bearer_principal

# Nonce — token_urlsafe(16): 22 символа; запас на смену длины.
NONCE_MAX = NONCE_BYTES * 4


class DecisionBody(Strict):
    """The nonce of the card the person decided on."""

    nonce: str = Field(min_length=1, max_length=NONCE_MAX)


class ActionOut(Out):
    """A card as it stands after the decision."""

    id: UUID
    tool: str
    status: PublicStatus
    outcome: str | None = Field(description="The code of an item that did not succeed.")
    nonce: str
    warning: bool = Field(description="Approve on the screen only, after a careful look.")
    taint: str | None = Field(description="The label of the text the run read before it.")
    reversibility: str
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None
    run_id: UUID | None = Field(description="The run whose stream carries the outcome.")


def action_out(decided: Decided) -> ActionOut:
    """The card the cabinet shows."""
    record = decided.record
    return ActionOut.model_validate(action_card(record) | {"run_id": record.run_id})


def build_actions_router(decisions: ActionDecisions, ports: PortDirectory) -> APIRouter:
    """The routes of the person's decisions on cards."""
    router = APIRouter(prefix="/v1/agent/actions", tags=["agent"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("/{action_id}/approve")
    async def approve_action(principal: person, action_id: UUID, body: DecisionBody) -> ActionOut:
        """Approve the card; its outcome within 20 s, or `executing`."""
        return action_out(await decisions.approve(principal, action_id, body.nonce))

    @router.post("/{action_id}/reject")
    async def reject_action(principal: person, action_id: UUID, body: DecisionBody) -> ActionOut:
        """Reject the card; nothing is changed."""
        return action_out(await decisions.reject(principal, action_id, body.nonce))

    return router
