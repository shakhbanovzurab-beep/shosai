"""Leo's `meetings` toolset: the live calls, a call started and ended once each (A13, MR-D8)."""

import uuid
from datetime import UTC, datetime, timedelta

from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.agent_tools.results import PlannedEffect, ToolError, ToolErrorCode
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.meetings.application.rooms import RoomBook
from shosai.features.meetings.application.video_server import RoomSpec
from shosai.features.meetings.channels.agent_specs import EndCall, NoArguments, StartCall
from shosai.features.meetings.channels.agent_tools import MeetingTools
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from shosai.features.workspaces.contracts import MEMBERSHIP_READER
from tests.features.meetings.room_bench import NOW, ORIGIN, RoomsBench
from tests.features.meetings.room_kit import add_room, room_row


def tools(bench: RoomsBench) -> MeetingTools:
    """The toolset's handlers over the bench's homes and SFU double."""
    ports = PortDirectory()
    ports.install([MEMBERSHIP_READER.bind(bench.spaces)])
    ledger = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    transactions = bench.homes.transactions
    book = RoomBook(transactions, (ledger, ports), bench.sfu, lambda: NOW)
    items = ActionItems(ledger, EventOutbox(EventTypes([ActionItemExecuted])))
    return MeetingTools(transactions, (book, items, bench.sfu), ORIGIN, lambda: NOW)


def context(who: uuid.UUID) -> ToolContext:
    """A call of the person's run."""
    return ToolContext(
        TenancyScope(Home.RU, who), uuid.uuid4(), datetime.now(UTC) + timedelta(seconds=30)
    )


async def test_a_call_starts_once_for_its_item_with_the_title_on_its_card(
    rooms_bench: RoomsBench,
) -> None:
    owner, meeting = uuid.uuid4(), tools(rooms_bench)

    planned = await meeting.plan_start(StartCall(title="  Design review "), context(owner))
    assert isinstance(planned, PlannedEffect)
    preview = await meeting.preview_start(planned, context(owner))
    first = await meeting.start(planned, context(owner), "action-1:0")
    again = await meeting.start(planned, context(owner), "action-1:0")
    too_long = await meeting.plan_start(StartCall.model_construct(title="x" * 201), context(owner))

    assert (preview.key, preview.params) == (
        "agent.meetings.start_call",
        {"title": "Design review"},
    )
    assert first.output is not None
    assert again.output == first.output
    assert first.output.invite_link.startswith(f"{ORIGIN}/meet/")
    assert first.output.join_path.startswith("/app/meet/")
    async with rooms_bench.homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        rooms = (await session.scalars(select(RoomRecord))).all()
    assert [(room.title, room.state) for room in rooms] == [("Design review", "open")]
    assert isinstance(too_long, ToolError)


async def test_the_live_calls_and_a_call_ended_for_everyone(rooms_bench: RoomsBench) -> None:
    owner, stranger, meeting = uuid.uuid4(), uuid.uuid4(), tools(rooms_bench)
    room = await add_room(rooms_bench.homes, room_row(owner, title="Standup"))
    await rooms_bench.sfu.create_room(RoomSpec(room.lk_room_name, 4, "{}"))
    rooms_bench.sfu.seat(room.lk_room_name, ["guest-0a1b2c3d4e5f__0a1b2c3d", "EG_recorder"])

    listed = await meeting.listed(NoArguments(), context(owner))
    hidden = await meeting.plan_end(EndCall(room_id=room.id), context(stranger))
    planned = await meeting.plan_end(EndCall(room_id=room.id), context(owner))
    assert isinstance(planned, PlannedEffect)
    preview = await meeting.preview_end(planned, context(owner))
    ended = await meeting.end(planned, context(owner), "action-2:0")
    again = await meeting.end(planned, context(owner), "action-2:0")
    after = await meeting.plan_end(EndCall(room_id=room.id), context(owner))

    assert listed.output is not None
    assert [(call.room_id, call.title, call.participants) for call in listed.output.calls] == [
        (room.id, "Standup", 2)
    ]
    assert isinstance(hidden, ToolError)
    assert hidden.code is ToolErrorCode.NOT_FOUND
    assert preview.params == {"title": "Standup", "people": 1}
    assert ended.output is not None
    assert again.output == ended.output
    assert room.lk_room_name in rooms_bench.sfu.deleted
    assert isinstance(after, ToolError)
    assert after.code is ToolErrorCode.CONFLICT
