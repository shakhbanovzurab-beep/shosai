"""The summary: an empty memory answers an empty summary with no model call, a summary that
fails its checks is not kept, a change makes it stale and queues one rewrite, and memory off or
no consent write nothing (memory step 7)."""

import uuid

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.summaries import Written
from shosai.features.memory.infrastructure.metrics import SummaryTrigger
from tests.features.billing.people_bench import bearer
from tests.features.memory.summary_bench import SummaryBench

SUMMARY = {
    "sections": [{"title": "Food", "body": "You are vegetarian and you like tea."}],
    "suggestions": ["What do I eat?"],
}


async def test_an_empty_memory_has_an_empty_summary_without_a_model_call(
    summary_bench: SummaryBench,
) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)

    view = await summary_bench.summaries.view(scope)
    written = await summary_bench.summaries.write(scope, SummaryTrigger.REFRESH)

    assert (view.summary.sections, view.stale, view.updated_at) == ((), False, None)
    assert written is Written.EMPTY
    assert summary_bench.writer.asked == []
    assert summary_bench.queued == []


async def test_a_written_summary_turns_stale_on_a_change_and_queues_one_rewrite(
    summary_bench: SummaryBench,
) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    summary_bench.consents.given.add(person)
    summary_bench.languages.of[person] = "ru"
    tea, _ = await summary_bench.add(
        person, [{"statement": "Likes tea"}, {"statement": "Is vegetarian", "pinned": True}]
    )
    summary_bench.writer.answers["memory.summary"] = [SUMMARY]

    written = await summary_bench.summaries.write(scope, SummaryTrigger.REFRESH)
    fresh = await summary_bench.summaries.view(scope)
    await summary_bench.http.delete(f"/v1/agent/memory/{tea}", headers=bearer((Home.RU, person)))
    recent = await summary_bench.summaries.view(scope)
    await summary_bench.written_hours_ago(person, 2)
    due = await summary_bench.summaries.view(scope)
    await summary_bench.summaries.view(scope)

    context, read = summary_bench.writer.asked[0]
    assert written is Written.WRITTEN
    assert read.splitlines()[1:] == ["F1 [fact] Is vegetarian", "F2 [fact] Likes tea"]
    assert context.cross_border_consent
    assert [section.title for section in fresh.summary.sections] == ["Food"]
    assert not fresh.stale
    assert recent.stale
    assert due.summary == fresh.summary
    assert summary_bench.queued == [(scope, SummaryTrigger.OPEN)]


async def test_a_summary_that_fails_its_checks_is_not_kept(summary_bench: SummaryBench) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    summary_bench.consents.given.add(person)
    await summary_bench.add(person, [{"statement": "Likes tea"}])
    marked = {"sections": [{"title": "Food", "body": "**Bold** claims"}], "suggestions": []}
    summary_bench.writer.answers["memory.summary"] = [SUMMARY, marked]

    first = await summary_bench.summaries.write(scope, SummaryTrigger.REFRESH)
    second = await summary_bench.summaries.write(scope, SummaryTrigger.REFRESH)
    kept = await summary_bench.summaries.view(scope)

    assert (first, second) == (Written.WRITTEN, Written.REFUSED)
    assert [section.body for section in kept.summary.sections] == [
        "You are vegetarian and you like tea."
    ]


async def test_memory_off_or_no_consent_writes_nothing_and_refresh_says_why(
    summary_bench: SummaryBench,
) -> None:
    off, refusing = uuid.uuid4(), uuid.uuid4()
    await summary_bench.add(off, [{"statement": "Likes tea"}])
    await summary_bench.add(refusing, [{"statement": "Likes tea"}])
    await summary_bench.switch.turn(Principal(off, Home.RU, 0), enabled=False)

    answers = [
        await summary_bench.http.post(
            "/v1/agent/memory/summary/refresh", headers=bearer((Home.RU, person))
        )
        for person in (off, refusing)
    ]

    assert [(answer.status_code, answer.json()["error"]["code"]) for answer in answers] == [
        (409, "memory_off"),
        (403, "consent_required"),
    ]
    assert summary_bench.writer.asked == []


async def test_the_summary_route_reads_without_a_model(summary_bench: SummaryBench) -> None:
    person = uuid.uuid4()
    await summary_bench.add(person, [{"statement": "Likes tea"}])

    answer = await summary_bench.http.get(
        "/v1/agent/memory/summary", headers=bearer((Home.RU, person))
    )

    assert answer.status_code == 200
    assert answer.json() == {"sections": [], "suggestions": [], "updated_at": None, "stale": True}
    assert summary_bench.writer.asked == []
    assert summary_bench.queued == [(TenancyScope(Home.RU, person), SummaryTrigger.OPEN)]
