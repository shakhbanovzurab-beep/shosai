"""A slice's write as a card without a model round, and a tool's artifact (AG-R2, AG-R1; 9b2).

A write a slice plans through `ActionProposals` shows the same card a turn would, joins the
answer it belongs to, is the same card again for the same origin key, and executes once on
approval, leaving a note in the thread; a refusal is the tool's error code. An artifact a tool
hands over reaches the stream and stays with the answer by its reference.
"""

import uuid
from typing import Final

import pytest
from prometheus_client import CollectorRegistry
from pydantic import JsonValue

from shosai.core.agent_tools.sources import ArtifactKind, ArtifactRef
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.proposal_port import PortProposals
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.contracts import ProposalOrigin, ProposalRefusedError, ProposalRequest
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, stream_of
from tests.features.billing.people_bench import bearer

SEARCH: Final = ("notes__search", '{"query": "digest"}')


def port_of(bench: ActionBench) -> PortProposals:
    """The port as the module binds it, over the bench's catalog and ports."""
    turns = bench.turns
    cards = ActionCards(turns.catalog, turns.ports)
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    threads = Threads(turns.homes.transactions, (turns.ports, effects))
    return PortProposals(turns.homes.transactions, (turns.catalog, cards, threads))


async def answered(bench: ActionBench, person: uuid.UUID) -> tuple[str, uuid.UUID]:
    """A thread with one answer: the thread and the answer's id."""
    thread = await bench.turns.thread(person)
    bench.turns.model.scripts = [saying("Here is the digest.")]
    events = stream_of(await bench.turns.ask(person, thread, "Digest, please."))
    return thread, uuid.UUID(events[0][2]["reply_id"])


def asked(
    person: uuid.UUID,
    where: tuple[str, uuid.UUID],
    arguments: dict[str, JsonValue] | None = None,
    origin_key: str = "digest-1:item-1",
) -> ProposalRequest:
    """A request of the probe's write for the person, under an answer of a thread."""
    thread, reply = where
    return ProposalRequest(
        scope=TenancyScope(HOME, person), thread_id=uuid.UUID(thread), message_id=reply,
        tool="tasks.create", arguments=arguments or {"query": "Call Anna"},
        origin=ProposalOrigin.PROPOSAL_PORT, origin_key=origin_key, language="en",
    )  # fmt: skip


async def test_a_slice_s_write_is_the_turn_s_card_and_executes_once(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn_card = (await action_bench.paused_turn(person))["card"]
    thread, reply = await answered(action_bench, person)
    port = port_of(action_bench)

    card = await port.propose(asked(person, (thread, reply)))
    again = await port.propose(asked(person, (thread, reply)))
    approved = await action_bench.decide(
        person, {"id": str(card.id), "nonce": card.nonce}, "approve"
    )
    await action_bench.queue.settle()
    history = await action_bench.turns.http.get(
        f"/v1/agent/threads/{thread}/messages", headers=bearer((HOME, person))
    )
    rows = [(m["role"], [a["id"] for a in m["actions"]]) for m in history.json()["items"]]

    assert (card.title, card.space, card.fields) == (
        turn_card["title"], turn_card["space"], tuple(
            (row["label"], row["value"]) for row in turn_card["preview"]["fields"]
        ),
    )  # fmt: skip
    assert (card.warning, card.taint, card.origin) == (False, None, ProposalOrigin.PROPOSAL_PORT)
    assert again.id == card.id
    assert approved.json()["status"] == "succeeded"
    assert action_bench.turns.tools.executed[-1] == f"{card.id}:0"
    assert action_bench.turns.tools.executed.count(f"{card.id}:0") == 1
    assert rows[:2] == [("server", [str(card.id)]), ("assistant", [str(card.id)])]


async def test_a_refused_plan_is_the_tool_s_error_code(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    thread, reply = await answered(action_bench, person)
    port = port_of(action_bench)

    with pytest.raises(ProposalRefusedError) as invalid:
        await port.propose(asked(person, (thread, reply), {"wrong": 1}))
    action_bench.turns.tools.refuse_plan = True
    with pytest.raises(ProposalRefusedError) as forbidden:
        await port.propose(asked(person, (thread, reply), origin_key="digest-1:item-2"))

    assert invalid.value.params == {"reason": "invalid_arguments"}
    assert forbidden.value.params == {"reason": "forbidden"}


async def test_an_artifact_reaches_the_stream_and_stays_with_the_answer(
    action_bench: ActionBench,
) -> None:
    person, chat, space = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    digest = ArtifactRef(
        ArtifactKind.CHAT_DIGEST, "digest-1", "The week in #launch",
        {"workspace_id": str(space), "chat_id": str(chat)},
    )  # fmt: skip
    action_bench.turns.tools.artifacts = [digest]
    thread = await action_bench.turns.thread(person)
    action_bench.turns.model.scripts = [calling(SEARCH), saying("The digest is above.")]

    events = stream_of(await action_bench.turns.ask(person, thread, "The chat's week?"))
    history = await action_bench.turns.http.get(
        f"/v1/agent/threads/{thread}/messages", headers=bearer((HOME, person))
    )
    expected = {
        "kind": "chat_digest", "ref": "digest-1", "alt": "The week in #launch",
        "workspace_id": str(space), "chat_id": str(chat),
    }  # fmt: skip

    assert [data for kind, _, data in events if kind == "artifact"] == [expected]
    assert history.json()["items"][0]["artifacts"] == [expected]
