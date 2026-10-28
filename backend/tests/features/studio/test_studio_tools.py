"""Leo's `studio` toolset (studio step 13): the person's "About you" read and rewritten on a
card — checked and frozen when proposed, applied once per item key, compensable, and never
offered over MCP."""

import uuid
from datetime import UTC, datetime, timedelta

from prometheus_client import CollectorRegistry

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolErrorCode
from shosai.core.agent_tools.spec import Reversibility, ToolEffect
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.channels.agent_tool_handlers import StudioTools
from shosai.features.studio.channels.agent_tools import (
    READ_CONTEXT,
    STUDIO_TOOLS,
    UPDATE_CONTEXT,
    ReadContext,
    UpdateContext,
)
from tests.harness.database_access import DatabaseAccess


def context_of(person: uuid.UUID) -> ToolContext:
    """A run's tool context in the person's Russian home."""
    return ToolContext(
        TenancyScope(Home.RU, person), uuid.uuid4(), datetime.now(UTC) + timedelta(seconds=30)
    )


def tools(homes: DatabaseAccess) -> StudioTools:
    """The toolset over the slot's homes."""
    items = ActionItems(
        EffectLedger(EffectKeyMetrics(CollectorRegistry())),
        EventOutbox(EventTypes([ActionItemExecuted])),
    )
    return StudioTools(homes.transactions, items)


def test_the_write_needs_a_card_and_is_never_offered_over_mcp() -> None:
    assert [spec.name for spec in STUDIO_TOOLS] == ["studio.read_context", "studio.update_context"]
    assert (READ_CONTEXT.effect, READ_CONTEXT.mcp, READ_CONTEXT.provenance) == (
        ToolEffect.READ,
        True,
        None,
    )
    assert (UPDATE_CONTEXT.effect, UPDATE_CONTEXT.reversibility) == (
        ToolEffect.WRITE,
        Reversibility.COMPENSABLE,
    )
    assert UPDATE_CONTEXT.mcp is False
    assert {len(wording.title) for wording in UPDATE_CONTEXT.previews} == {16}


async def test_a_proposed_text_is_frozen_trimmed_and_applied_once(homes: DatabaseAccess) -> None:
    studio, person = tools(homes), uuid.uuid4()
    context = context_of(person)

    before = await studio.read(ReadContext(), context)
    planned = await studio.plan(UpdateContext(content="  I lead a design team.  "), context)
    assert isinstance(planned, PlannedEffect)
    card = await studio.preview(planned, context)
    first = await studio.execute(planned, context, "item-1")
    again = await studio.execute(planned, context, "item-1")
    after = await studio.read(ReadContext(), context)

    assert before.output is not None
    assert (before.output.content, before.output.updated_at) == ("", None)
    assert (card.key, card.params) == (
        "agent.studio.update_context",
        {"content": "I lead a design team."},
    )
    assert first.output == again.output
    assert after.output is not None
    assert after.output.content == "I lead a design team."


async def test_someone_else_s_words_are_neither_read_nor_written(homes: DatabaseAccess) -> None:
    studio, owner, stranger = tools(homes), uuid.uuid4(), uuid.uuid4()
    planned = await studio.plan(UpdateContext(content="Mine."), context_of(owner))
    assert isinstance(planned, PlannedEffect)
    await studio.execute(planned, context_of(owner), "item-2")

    theirs = await studio.read(ReadContext(), context_of(stranger))

    assert theirs.output is not None
    assert theirs.output.content == ""


async def test_a_text_that_cannot_be_stored_is_refused_when_proposed(homes: DatabaseAccess) -> None:
    refused = await tools(homes).plan(
        UpdateContext.model_construct(content="x" * 4_001), context_of(uuid.uuid4())
    )

    assert refused == ToolError(ToolErrorCode.INVALID_ARGUMENTS)
