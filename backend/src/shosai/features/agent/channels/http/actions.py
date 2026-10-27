"""The person's cards: the inbox and one card, approve and reject (steps 9a, 9b; Leo §13.2).

A card (`LeoProposal`) is what the person decides with, in their language: the title and the
labelled fields its slice words, the space, the origin, how it can be undone, whether it asks
for a careful decision, the label of the text the run read before it, its state and its
times, and the nonce a decision carries. `GET /v1/agent/actions?status=` lists the person's
cards newest first by cursor — "Needs you" reads `status=proposed` — and `GET …/{id}` reads
one. `approve` answers within 20 s with the action's end, or `executing` when it takes longer —
the end follows as `action.updated` on the run's stream — with the run that resumes after it.
Errors use the platform's envelope: `action_not_found` (404: no card of the person by that id)
and `action_not_pending` (409: the card no longer waits, or it is not the one the person saw).
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_decisions import ActionDecisions
from shosai.features.agent.application.action_inbox import ActionInbox
from shosai.features.agent.channels.http.shapes import Out, Strict
from shosai.features.agent.domain.actions import NONCE_BYTES, PublicStatus
from shosai.features.identity.contracts import Principal, bearer_principal

# Nonce — token_urlsafe(16): 22 символа; запас на смену длины.
NONCE_MAX = NONCE_BYTES * 4


class DecisionBody(Strict):
    """The nonce of the card the person decided on."""

    nonce: str = Field(min_length=1, max_length=NONCE_MAX)


class OriginOut(Out):
    """Where the proposal came from."""

    kind: Literal["thread", "errand", "mcp"]
    app: str | None = Field(description="An outside client's name, for `mcp`.")


class FieldOut(Out):
    """One row of a card."""

    label: str
    value: str


class PreviewOut(Out):
    """What the change does, worded by its slice."""

    kind: Literal["fields"]
    fields: list[FieldOut]
    body: str | None = Field(description="A text the change sends or writes, shown as is.")


class ProposalOut(Out):
    """A card, in the person's language (`LeoProposal`)."""

    id: UUID
    tool: str
    title: str
    space: str = Field(description="Personal, or the workspace's name.")
    origin: OriginOut
    reversibility: Literal["reversible", "compensable", "irreversible"]
    warning: bool = Field(description="Approve on the screen only, after a careful look.")
    taint: str | None = Field(description="The label of the text the run read before it.")
    suspicious: bool = Field(
        default=False,
        description="Text the run read looked like it was giving Leo instructions.",
    )
    preview: PreviewOut
    status: PublicStatus
    outcome: str | None = Field(description="The code of an item that did not succeed.")
    nonce: str
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None


class DecidedOut(ProposalOut):
    """A card as it stands after the decision."""

    run_id: UUID | None = Field(description="The run whose stream carries the outcome.")


def build_actions_router(
    services: tuple[ActionDecisions, ActionInbox], ports: PortDirectory
) -> APIRouter:
    """The routes of the person's cards."""
    decisions, inbox = services
    router = APIRouter(prefix="/v1/agent/actions", tags=["agent"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("")
    async def list_actions(
        principal: person,
        page: PageParameters,
        status: Annotated[
            PublicStatus | None, Query(description="Only cards in this state.")
        ] = None,
    ) -> Page[ProposalOut]:
        """A page of the person's cards, newest first."""
        found = await inbox.page(principal, status, page)
        items = [ProposalOut.model_validate(card) for card in found.items]
        return Page(items=items, next_cursor=found.next_cursor)

    @router.get("/{action_id}")
    async def get_action(principal: person, action_id: UUID) -> ProposalOut:
        """One of the person's cards."""
        return ProposalOut.model_validate(await inbox.card(principal, action_id))

    @router.post("/{action_id}/approve")
    async def approve_action(principal: person, action_id: UUID, body: DecisionBody) -> DecidedOut:
        """Approve the card; its outcome within 20 s, or `executing`."""
        record = (await decisions.approve(principal, action_id, body.nonce)).record
        card = await inbox.decided(principal, record)
        return DecidedOut.model_validate(card | {"run_id": record.run_id})

    @router.post("/{action_id}/reject")
    async def reject_action(principal: person, action_id: UUID, body: DecisionBody) -> DecidedOut:
        """Reject the card; nothing is changed."""
        record = (await decisions.reject(principal, action_id, body.nonce)).record
        card = await inbox.decided(principal, record)
        return DecidedOut.model_validate(card | {"run_id": record.run_id})

    return router
