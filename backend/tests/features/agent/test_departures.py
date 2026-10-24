"""A workspace's threads follow the person's membership (AG-D3; agent step 4).

The departure is applied as the delivery applies it, in the scope `scope_of_departure`
names; the purge and the erasure run as the workers run them.
"""

import uuid
from datetime import datetime, timedelta

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.after_turn import AfterTurn
from shosai.features.agent.application.departures import Departures, scope_of_departure
from shosai.features.agent.channels.subscriptions import subscriptions
from shosai.features.workspaces.contracts.events import MemberRemoved
from shosai.features.workspaces.domain.memberships import RemovalReason
from tests.features.agent.thread_bench import HOME, ThreadBench
from tests.features.agent.turn_doubles import SentTasks
from tests.harness.connections import fetch_value

WEEK = timedelta(days=7)


def departure(org: uuid.UUID, member: uuid.UUID) -> MemberRemoved:
    """The event workspaces writes when the member leaves."""
    return MemberRemoved(
        org_id=org, user_id=member, membership_id=uuid.uuid4(), reason=RemovalReason.LEFT
    )


async def deliver(bench: ThreadBench, org: uuid.UUID, member: uuid.UUID, at: datetime) -> None:
    """The departure applied as its delivery applies it, twice: a redelivery changes nothing."""
    event = departure(org, member)
    scope = scope_of_departure(event, TenancyScope(HOME, member, org))
    for _ in range(2):
        async with bench.homes.transactions.begin(scope) as session:
            await Departures(bench.homes.transactions, bench.ports).follow(session, event, at)


async def visible(bench: ThreadBench, person: uuid.UUID, org: uuid.UUID) -> list[str]:
    """The ids the person's workspace list shows."""
    answer = await bench.call(
        person, "GET", f"/v1/agent/threads?scope=workspace&workspace_id={org}"
    )
    return [item["id"] for item in answer.json()["items"]]


async def stored(bench: ThreadBench, thread: str) -> tuple[object, object]:
    """Whether the thread's row is still there, and its erasure mark."""
    count = await fetch_value(
        bench.connection, "SELECT count(*) FROM agent_threads WHERE id = %s", (uuid.UUID(thread),)
    )
    mark = await fetch_value(
        bench.connection,
        "SELECT erase_after FROM agent_threads WHERE id = %s",
        (uuid.UUID(thread),),
    )
    return count, mark


async def test_a_departed_workspace_s_threads_vanish_at_once_and_return_with_it(
    thread_bench: ThreadBench,
) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await thread_bench.workspace(org, owner, member)
    thread = await thread_bench.thread(member, org)
    personal = await thread_bench.thread(member)

    await thread_bench.leave(org, member)
    hidden = await visible(thread_bench, member, org)
    route = await thread_bench.call(member, "GET", f"/v1/agent/threads/{thread}/messages")
    mine = await thread_bench.call(member, "GET", f"/v1/agent/threads/{personal}")
    await thread_bench.come_back(org, member)

    assert hidden == []
    assert (route.status_code, route.json()["error"]["code"]) == (404, "thread_not_found")
    assert mine.status_code == 200
    assert await visible(thread_bench, member, org) == [thread]


async def test_threads_of_a_workspace_left_for_7_days_are_erased(
    thread_bench: ThreadBench,
) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await thread_bench.workspace(org, owner, member)
    thread = await thread_bench.thread(member, org)
    kept = await thread_bench.thread(owner, org)
    await thread_bench.message(member, thread, "user", thread_bench.clock.now)
    await thread_bench.leave(org, member)
    left_at = thread_bench.clock.now

    await deliver(thread_bench, org, member, left_at)
    async with thread_bench.departures() as departures:
        thread_bench.clock.advance(WEEK - timedelta(minutes=1))
        early = await departures.purge(HOME)
        waiting = await stored(thread_bench, thread)
        thread_bench.clock.advance(timedelta(minutes=1))
        erased = await departures.purge(HOME)

    assert (early, waiting) == (0, (1, left_at + WEEK))
    assert erased == 1
    assert await stored(thread_bench, thread) == (0, None)
    assert await stored(thread_bench, kept) == (1, None)


async def test_a_member_back_within_7_days_keeps_the_threads(thread_bench: ThreadBench) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await thread_bench.workspace(org, owner, member)
    thread = await thread_bench.thread(member, org)
    await thread_bench.leave(org, member)
    await deliver(thread_bench, org, member, thread_bench.clock.now)

    await thread_bench.come_back(org, member)
    thread_bench.clock.advance(WEEK)
    async with thread_bench.departures() as departures:
        erased = await departures.purge(HOME)

    assert erased == 0
    assert await stored(thread_bench, thread) == (1, None)
    assert await visible(thread_bench, member, org) == [thread]


async def test_a_member_active_again_by_the_delivery_is_not_marked(
    thread_bench: ThreadBench,
) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await thread_bench.workspace(org, owner, member)
    thread = await thread_bench.thread(member, org)

    await deliver(thread_bench, org, member, thread_bench.clock.now)

    assert await stored(thread_bench, thread) == (1, None)


async def test_a_later_departure_moves_the_mark_later_never_earlier(
    thread_bench: ThreadBench,
) -> None:
    owner, member, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await thread_bench.workspace(org, owner, member)
    thread = await thread_bench.thread(member, org)
    await thread_bench.leave(org, member)
    first, second = thread_bench.clock.now, thread_bench.clock.now + timedelta(days=3)

    await deliver(thread_bench, org, member, second)
    await deliver(thread_bench, org, member, first)

    assert await stored(thread_bench, thread) == (1, second + WEEK)


async def test_a_deleted_workspace_s_threads_are_erased_at_once(
    thread_bench: ThreadBench,
) -> None:
    owner, member, org, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await thread_bench.workspace(org, owner, member)
    await thread_bench.workspace(other, owner)
    gone = [await thread_bench.thread(owner, org), await thread_bench.thread(member, org)]
    kept = [await thread_bench.thread(owner, other), await thread_bench.thread(member)]
    await thread_bench.message(member, gone[1], "user", thread_bench.clock.now)

    async with thread_bench.departures() as departures:
        erased = await departures.erase_workspace(HOME, org)
        again = await departures.erase_workspace(HOME, org)

    assert (erased, again) == (2, 0)
    assert [await stored(thread_bench, thread) for thread in gone] == [(0, None)] * 2
    assert [await stored(thread_bench, thread) for thread in kept] == [(1, None)] * 2


async def test_the_consumers_keep_their_names_and_the_departed_person_s_scope(
    thread_bench: ThreadBench,
) -> None:
    org, member, actor = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    departures = Departures(thread_bench.homes.transactions, thread_bench.ports)
    found = subscriptions(departures, AfterTurn(SentTasks()))
    scope = found[0].scope

    assert [entry.consumer for entry in found] == [
        "agent.follow_departure",
        "agent.after_turn",
        "agent.erase_with_workspace",
    ]
    assert scope is not None
    assert scope(departure(org, member), TenancyScope(HOME, actor)) == TenancyScope(
        HOME, member, org
    )
