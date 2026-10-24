"""What follows a turn: the title, the summary, and the run's numbers and spans (step 5b)."""

import uuid

from prometheus_client import CollectorRegistry

from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.after_turn import AfterTurn, ThreadTask
from shosai.features.agent.application.thread_care import ThreadCare
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.identity.contracts import CONSENT_READER
from tests.features.agent.test_context import text_of
from tests.features.agent.turn_bench import HOME, ROUTE, TurnBench, stream_of
from tests.features.agent.turn_doubles import SentTasks, Terms, Utility
from tests.harness.connections import fetch_rows

LONG = "word " * 700


async def thread_row(bench: TurnBench, thread: str) -> dict[str, object]:
    """The thread's title, its source, its summary and the last message folded."""
    rows = await fetch_rows(
        bench.connection,
        "SELECT title, title_source, summary, summary_upto FROM agent_threads WHERE id = %s",
        (uuid.UUID(thread),),
    )
    return dict(rows[0])


def care(bench: TurnBench, utility: Utility) -> ThreadCare:
    """The thread's care with the utility model double and the bench's consents."""
    ports = PortDirectory()
    ports.install([CONSENT_READER.bind(Terms())])
    return ThreadCare(bench.homes.transactions, (utility, ROUTE), ports)


async def follow(bench: TurnBench, person: uuid.UUID, thread: str) -> list[str]:
    """The tasks a completed turn of the thread sends."""
    sent = SentTasks()
    async with bench.homes.transactions.begin(TenancyScope(HOME, person)) as session:
        event = TurnCompleted(thread_id=uuid.UUID(thread), run_id=uuid.uuid4(), user_id=person)
        await AfterTurn(sent).follow(session, event, HOME)
    return [name for name, _ in sent.sent]


async def test_a_first_answer_names_the_thread_unless_the_person_did(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    named, renamed = await turn_bench.thread(person), await turn_bench.thread(person)
    for thread in (named, renamed):
        await turn_bench.ask(person, thread, "What is a vector database?")
    after_first = await follow(turn_bench, person, named)
    await turn_bench.http.patch(
        f"/v1/agent/threads/{renamed}",
        json={"title": "Mine"},
        headers={"Authorization": f"Bearer person:{person}:{HOME.value}"},
    )
    utility = Utility(['"Vector databases."', "Ignored"])

    for thread in (named, renamed):
        await care(turn_bench, utility).title(
            ThreadTask(home=HOME, user_id=person, thread_id=uuid.UUID(thread))
        )
    await turn_bench.ask(person, named, "And a graph database?")

    assert after_first == ["agent.title_thread"]
    assert await follow(turn_bench, person, named) == []
    assert (await thread_row(turn_bench, named))["title"] == "Vector databases"
    assert (await thread_row(turn_bench, named))["title_source"] == "model"
    assert (await thread_row(turn_bench, renamed))["title"] == "Mine"
    assert len(utility.requests) == 1


async def test_a_long_thread_folds_into_a_summary_that_keeps_its_first_question(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    await turn_bench.ask(person, thread, "Oldest question")
    for _ in range(4):
        await turn_bench.ask(person, thread, LONG)
    task = ThreadTask(home=HOME, user_id=person, thread_id=uuid.UUID(thread))
    utility = Utility(["They discussed words.", "Unused"])

    sent = await follow(turn_bench, person, thread)
    await care(turn_bench, utility).compact(task)
    folded = await thread_row(turn_bench, thread)
    await care(turn_bench, utility).compact(task)
    await turn_bench.ask(person, thread, "Newest question")
    request = turn_bench.model.calls[-1]

    assert "agent.compact_thread" in sent
    assert str(folded["summary"]).startswith(
        "The conversation began with this question:\nOldest question\n\nThey discussed words."
    )
    assert folded["summary_upto"] is not None
    assert await thread_row(turn_bench, thread) == folded
    assert len(utility.requests) == 1
    assert "<<untrusted source=memory id=" in text_of(utility.requests[0], 1)
    assert "They discussed words." in text_of(request, 0)
    assert "Oldest question" not in [
        text_of(request, i) for i in range(1, len(request.messages) - 1)
    ]


def sample(registry: CollectorRegistry, name: str, **labels: str) -> float:
    """A metric's sample, 0 when absent."""
    return registry.get_sample_value(name, labels) or 0.0


async def test_a_turn_records_its_model_cost_times_numbers_and_spans(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    registry, spans = turn_bench.observed

    events = stream_of(await turn_bench.ask(person, thread))
    run_id = events[0][2]["run_id"]
    row = (
        await fetch_rows(
            turn_bench.connection,
            "SELECT model, cost_micro_usd, ttft_ms, overhead_ms, duration_ms FROM agent_runs"
            " WHERE id = %s",
            (uuid.UUID(run_id),),
        )
    )[0]
    names = {span.name: span for span in spans.get_finished_spans()}

    assert (row["model"], row["cost_micro_usd"]) == ("probe/leo", 1_200)
    assert row["ttft_ms"] is not None
    assert 0 <= row["overhead_ms"] <= row["duration_ms"]
    assert sample(registry, "shosai_agent_turns_total", channel="web", outcome="answered") == 1
    assert sample(registry, "shosai_agent_platform_overhead_seconds_count", home="eu") == 1
    assert sample(registry, "shosai_agent_queue_pickup_seconds_count") == 1
    assert sample(registry, "shosai_agent_context_tokens_count", segment="question") == 1
    assert {"agent.run", "agent.context"} <= set(names)
    assert names["agent.run"].attributes == {"agent.run_id": run_id, "agent.turn_kind": "new"}
