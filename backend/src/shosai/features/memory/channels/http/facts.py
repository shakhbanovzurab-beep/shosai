"""What Leo remembers, fact by fact: `/v1/agent/memory*` (memory plan §3.3, step 3).

The cabinet lists facts and candidates by cursor with the counts its settings row shows,
filtered on the server; edits a statement (a new fact takes the old one's place), pins,
accepts a candidate, forgets one fact or everything, and turns down the draft's carried-over
candidates in one go. The switch is `GET` and `PATCH /v1/agent/memory/settings`. Errors use
the platform's envelope: `memory_fact_not_found` for a fact the person cannot change — gone,
another person's or never there — `memory_fact_invalid`, `invalid_cursor`, `validation_error`,
`idempotency_key_reused`. No route is gated by plan: a person's memory is never held back.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.pagination.page import PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.memory.application.fact_changes import FactChanges
from shosai.features.memory.application.fact_list import Counts, FactLists, FactQuery, FactView
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.domain.facts import STATEMENT_MAX, FactKind, FactStatus, MemorySource

WORDS_MAX = 200


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class MemorySourceOut(Out):
    """Where a fact came from."""

    kind: MemorySource
    title: str | None = Field(description="The meeting's title for a meeting's fact, else null.")
    thread_id: UUID | None = Field(description="The conversation a fact came from, if any.")
    message_id: UUID | None = Field(description="The message a fact came from, if any.")


class MemoryFactOut(Out):
    """A fact, or a candidate waiting for the person."""

    id: UUID
    kind: FactKind
    statement: str
    status: Literal["candidate", "active"]
    pinned: bool
    source: MemorySourceOut
    created_at: datetime


class MemoryCountsOut(Out):
    """How many facts, waiting candidates and carried-over candidates the person has."""

    active: int
    candidates: int
    imported: int


class FactsPageOut(Out):
    """A page of facts, the next page's cursor and the person's counts."""

    items: list[MemoryFactOut]
    next_cursor: str | None
    counts: MemoryCountsOut


class FactPatch(Strict):
    """A new statement, a pin, or both."""

    statement: str | None = Field(default=None, min_length=1, max_length=STATEMENT_MAX)
    pinned: bool | None = None


class MemorySettingsOut(Out):
    """The memory switch."""

    enabled: bool = Field(description="Off: Leo neither uses nor saves memories; none is deleted.")


class MemorySettingsPatch(Strict):
    """Turn memory on or off."""

    enabled: bool


def fact_out(view: FactView) -> MemoryFactOut:
    """The contract's shape of a fact."""
    return MemoryFactOut(
        id=view.id,
        kind=view.kind,
        statement=view.statement,
        status="candidate" if view.status is FactStatus.CANDIDATE else "active",
        pinned=view.pinned,
        source=MemorySourceOut(
            kind=view.source, title=view.title, thread_id=view.thread_id, message_id=view.message_id
        ),
        created_at=view.created_at,
    )


def counts_out(counts: Counts) -> MemoryCountsOut:
    """The contract's shape of the counts."""
    return MemoryCountsOut(
        active=counts.active, candidates=counts.candidates, imported=counts.imported
    )


def fact_query(
    status: Literal["candidate", "active"] | None = None,
    kind: FactKind | None = None,
    source: Annotated[
        Literal["imported"] | None, Query(description="`imported`: the carried-over candidates.")
    ] = None,
    thread_id: Annotated[
        UUID | None, Query(description="A conversation's waiting candidates.")
    ] = None,
    q: Annotated[str | None, Query(max_length=WORDS_MAX, description="Words in the fact.")] = None,
) -> FactQuery:
    """The list's filters, read from the query string."""
    return FactQuery(
        status=FactStatus(status) if status else None,
        kind=kind,
        imported=source == "imported",
        thread_id=thread_id,
        words=q.strip() if q else None,
    )


def build_memory_router(
    services: tuple[FactLists, FactChanges, MemorySwitch], ports: PortDirectory
) -> APIRouter:
    """Settings > Memory's facts and switch."""
    lists, changes, switch = services
    router = APIRouter(prefix="/v1/agent/memory", tags=["memory"])
    signed_in = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("")
    async def list_memory_facts(
        principal: signed_in, page: PageParameters, query: Annotated[FactQuery, Depends(fact_query)]
    ) -> FactsPageOut:
        """Your facts and candidates, candidates first, newest first."""
        found, counts = await lists.page(principal, query, page)
        return FactsPageOut(
            items=[fact_out(view) for view in found.items],
            next_cursor=found.next_cursor,
            counts=counts_out(counts),
        )

    @router.get("/settings")
    async def get_memory_settings(principal: signed_in) -> MemorySettingsOut:
        """Whether your memory is on."""
        return MemorySettingsOut(enabled=await switch.read(principal))

    @router.patch("/settings")
    async def patch_memory_settings(
        principal: signed_in, body: MemorySettingsPatch
    ) -> MemorySettingsOut:
        """Turn your memory on or off; off keeps every fact."""
        return MemorySettingsOut(enabled=await switch.turn(principal, enabled=body.enabled))

    @router.post("/imported/turn-down", status_code=HTTPStatus.NO_CONTENT, response_class=Response)
    async def turn_down_imported_facts(principal: signed_in) -> None:
        """Turn down every candidate carried over from your earlier memory."""
        await changes.turn_down_imported(principal)

    @router.delete("", status_code=HTTPStatus.NO_CONTENT, response_class=Response)
    async def forget_all_memory_facts(principal: signed_in) -> None:
        """Forget everything Leo remembers about you."""
        await changes.forget_all(principal)

    @router.patch("/{fact_id}")
    async def patch_memory_fact(
        principal: signed_in, fact_id: UUID, body: FactPatch, key: IdempotencyKeyHeader
    ) -> MemoryFactOut:
        """Correct a fact — a new one takes its place — or pin it."""
        view = await changes.edit(principal, fact_id, (body.statement, body.pinned), key)
        return fact_out(view)

    @router.post("/{fact_id}/accept")
    async def accept_memory_fact(principal: signed_in, fact_id: UUID) -> MemoryFactOut:
        """Remember a candidate."""
        return fact_out(await changes.accept(principal, fact_id))

    @router.delete("/{fact_id}", status_code=HTTPStatus.NO_CONTENT, response_class=Response)
    async def forget_memory_fact(principal: signed_in, fact_id: UUID) -> None:
        """Forget a fact, or turn a candidate down."""
        await changes.forget(principal, fact_id)

    return router
