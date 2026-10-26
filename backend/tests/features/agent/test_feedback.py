"""Ratings under Leo's answers and the evaluation cases they may make (agent step 11a; AG-D13)."""

import uuid
from datetime import timedelta
from typing import Any

import httpx

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.case_care import consent_changed
from shosai.features.agent.application.eval_cases import PROMPT_VERSION
from shosai.features.agent.domain.feedback import Rating
from shosai.features.identity.contracts import ConsentChanged
from tests.features.agent.feedback_bench import FeedbackBench, RunFacts
from tests.features.agent.thread_bench import HOME
from tests.harness.connections import fetch_rows

WORDS = ("Anna Petrova here: what did we agree with Northwind?", "Anna Petrova agreed €18.", "€18.")


async def cases(bench: FeedbackBench, answer: str) -> list[dict[str, Any]]:
    """The answer's cases as the home keeps them."""
    return list(
        await fetch_rows(
            bench.connection,
            'SELECT rating, language, model, tier, toolsets, prompt_version, "case", created_at'
            " FROM agent_eval_cases WHERE message_id = %s",
            (uuid.UUID(answer),),
        )
    )


async def shared(bench: FeedbackBench, answer: str) -> list[bool]:
    """The answer's rating row: whether it shares."""
    rows = await fetch_rows(
        bench.connection,
        "SELECT shared FROM agent_feedback WHERE message_id = %s",
        (uuid.UUID(answer),),
    )
    return [bool(row["shared"]) for row in rows]


async def rate(
    bench: FeedbackBench, person: uuid.UUID, answer: str, rating: str | None
) -> httpx.Response:
    """`PUT` the rating, or `DELETE` it for None."""
    path = f"/v1/agent/messages/{answer}/feedback"
    if rating is None:
        return await bench.call(person, "DELETE", path)
    return await bench.call(person, "PUT", path, json={"rating": rating})


def counted(bench: FeedbackBench, rating: str) -> float:
    """The ratings counted, by rating, over every label set."""
    total = 0.0
    for metric in bench.registry.collect():
        if metric.name == "shosai_agent_ratings":
            total += sum(
                sample.value
                for sample in metric.samples
                if sample.name.endswith("_total") and sample.labels.get("rating") == rating
            )
    return total


async def test_a_rating_without_consent_is_kept_and_shared_with_nobody(
    feedback_bench: FeedbackBench,
) -> None:
    person = uuid.uuid4()
    thread = await feedback_bench.thread(person)
    answer, _ = await feedback_bench.turn(person, thread, WORDS)

    first = await rate(feedback_bench, person, answer, "useful")
    again = await rate(feedback_bench, person, answer, "useful")
    history = await feedback_bench.call(person, "GET", f"/v1/agent/threads/{thread}/messages")

    assert first.json() == {"rating": "useful", "shared": False} == again.json()
    rows = {row["id"]: row["feedback"] for row in history.json()["items"]}
    assert rows[answer] == "useful"
    assert await cases(feedback_bench, answer) == []
    assert counted(feedback_bench, "useful") == 1


async def test_a_consented_rating_makes_one_masked_case_that_follows_the_rating(
    feedback_bench: FeedbackBench,
) -> None:
    person = uuid.uuid4()
    feedback_bench.people.improving.add(person)
    feedback_bench.people.names_by_person[person] = "Anna Petrova"
    thread = await feedback_bench.thread(person)
    routing = {"selected": ["notes"], "loaded": ["tasks"]}
    made = RunFacts(
        model="m-1", tier="standard", language="de", routing=routing,
        sources=[{"kind": "meeting", "title": "Call with Anna", "org_id": None}],
    )  # fmt: skip
    answer, _ = await feedback_bench.turn(person, thread, WORDS, made)

    useful = await rate(feedback_bench, person, answer, "useful")
    changed = await rate(feedback_bench, person, answer, "not_useful")
    [case] = await cases(feedback_bench, answer)

    assert (useful.json()["shared"], changed.json()) == (
        True, {"rating": "not_useful", "shared": True},
    )  # fmt: skip
    assert (case["rating"], case["language"], case["model"], case["tier"]) == (
        "not_useful", "de", "m-1", "standard",
    )  # fmt: skip
    assert (case["toolsets"], case["prompt_version"]) == (["notes", "tasks"], PROMPT_VERSION)
    kept = case["case"]
    assert kept["question"] == "[name] here: what did we agree with Northwind?"
    assert kept["rounds"][0]["results"] == [
        {"tool": "notes.search", "digest": "[name] agreed €18."}
    ]
    assert "Anna" not in str(kept)
    assert (kept["answer"], kept["sources"]) == (
        "€18.",
        [{"kind": "meeting", "title": "Call with [name]"}],
    )
    assert await shared(feedback_bench, answer) == [True]


async def test_an_answer_built_on_a_workspace_makes_no_case(feedback_bench: FeedbackBench) -> None:
    person = uuid.uuid4()
    feedback_bench.people.improving.add(person)
    thread = await feedback_bench.thread(person)
    org = str(uuid.uuid4())
    sources: list[dict[str, str | None]] = [
        {"kind": "meeting", "title": "Team call", "org_id": org}
    ]
    answer, _ = await feedback_bench.turn(person, thread, WORDS, RunFacts(sources=sources))

    rated = await rate(feedback_bench, person, answer, "not_useful")

    assert rated.json() == {"rating": "not_useful", "shared": False}
    assert await cases(feedback_bench, answer) == []


async def test_removing_the_rating_withdrawing_consent_or_deleting_the_thread_erases_the_case(
    feedback_bench: FeedbackBench,
) -> None:
    person = uuid.uuid4()
    feedback_bench.people.improving.add(person)
    thread = await feedback_bench.thread(person)
    removed, _ = await feedback_bench.turn(person, thread, WORDS)
    withdrawn, _ = await feedback_bench.turn(person, thread, WORDS)
    other = await feedback_bench.thread(person)
    deleted, _ = await feedback_bench.turn(person, other, WORDS)
    for answer in (removed, withdrawn, deleted):
        assert (await rate(feedback_bench, person, answer, "useful")).json()["shared"] is True

    gone = await rate(feedback_bench, person, removed, None)
    again = await rate(feedback_bench, person, removed, None)
    feedback_bench.people.improving.discard(person)
    event = ConsentChanged(user_id=person, kind="improve_models", granted=False)
    async with feedback_bench.homes.transactions.begin(TenancyScope(HOME, person)) as session:
        await consent_changed(session, event)
    await feedback_bench.call(person, "DELETE", f"/v1/agent/threads/{other}")

    assert (gone.status_code, again.status_code) == (204, 204)
    assert [await cases(feedback_bench, a) for a in (removed, withdrawn, deleted)] == [[], [], []]
    assert await shared(feedback_bench, removed) == []
    assert await shared(feedback_bench, withdrawn) == [False]
    assert await shared(feedback_bench, deleted) == []


async def test_only_the_persons_answers_are_rated(feedback_bench: FeedbackBench) -> None:
    person, stranger = uuid.uuid4(), uuid.uuid4()
    thread = await feedback_bench.thread(person)
    answer, question = await feedback_bench.turn(person, thread, WORDS)

    refused = [
        await rate(feedback_bench, person, question, "useful"),
        await rate(feedback_bench, stranger, answer, "useful"),
        await rate(feedback_bench, stranger, answer, None),
        await rate(feedback_bench, person, str(uuid.uuid4()), "useful"),
    ]
    invalid = await feedback_bench.call(
        person, "PUT", f"/v1/agent/messages/{answer}/feedback", json={"rating": "great"}
    )

    assert [(r.status_code, r.json()["error"]["code"]) for r in refused] == [
        (404, "message_not_found")
    ] * 4
    assert invalid.status_code == 422


async def test_the_daily_purge_erases_cases_past_their_year(feedback_bench: FeedbackBench) -> None:
    person = uuid.uuid4()
    feedback_bench.people.improving.add(person)
    thread = await feedback_bench.thread(person)
    old, _ = await feedback_bench.turn(person, thread, WORDS)
    recent, _ = await feedback_bench.turn(person, thread, WORDS)
    for answer in (old, recent):
        await rate(feedback_bench, person, answer, "useful")
    await feedback_bench.connection.execute(
        "UPDATE agent_eval_cases SET created_at = created_at - interval '366 days'"
        " WHERE message_id = %s",
        (uuid.UUID(old),),
    )

    async with feedback_bench.purge() as purge:
        feedback_bench.clock.advance(timedelta(minutes=1))
        erased = await purge.purge(HOME)
        again = await purge.purge(HOME)

    assert (erased, again) == (1, 0)
    assert (await cases(feedback_bench, old), len(await cases(feedback_bench, recent))) == ([], 1)
    assert await shared(feedback_bench, old) == [False]


async def test_the_host_counts_cases_without_text_and_every_read_is_audited(
    feedback_bench: FeedbackBench,
) -> None:
    person = uuid.uuid4()
    feedback_bench.people.improving.add(person)
    thread = await feedback_bench.thread(person)
    answer, _ = await feedback_bench.turn(person, thread, WORDS, RunFacts(language="ru"))
    await rate(feedback_bench, person, answer, "not_useful")

    async with feedback_bench.reads() as reads:
        counts = await reads.counts()
        refs = await reads.refs(Rating.NOT_USEFUL, "ru", 10)
        none = await reads.refs(Rating.USEFUL, None, 10)
        found = await reads.find(refs[0].case_id)
        stored = await reads.read(refs[0])
        unknown = await reads.find(uuid.uuid4())
    audited = await fetch_rows(
        feedback_bench.connection,
        "SELECT payload FROM outbox_messages WHERE event_type = 'identity.operator.acted'",
    )

    mine = [count for count in counts if count.language == "ru"]
    assert [(count.rating, count.cases) for count in mine] == [(Rating.NOT_USEFUL, 1)]
    assert (len(refs), none, found == refs[0], unknown) == (1, [], True, None)
    assert stored is not None
    assert stored.case["answer"] == WORDS[2]
    assert [
        (row["payload"]["action"], row["payload"]["subject_id"])
        for row in audited
        if row["payload"]["target_user_id"] == str(person)
    ] == [("eval_case_read", str(stored.id))]
