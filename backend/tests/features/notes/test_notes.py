"""The notes after a meeting against a recorded model: findings, write-up, map (notes step 6)."""

import uuid
from datetime import date, timedelta
from http import HTTPStatus

from shosai.core.kernel.homes import Home
from shosai.features.notes.application.pipeline import StageWork
from shosai.features.notes.domain.runs import RunSource, RunState, Stage
from shosai.features.notes.domain.transcript_text import numbered, rendered
from shosai.features.notes.infrastructure.prompts import ASK_AGAIN
from tests.features.notes.meeting_bench import bearer
from tests.features.notes.notes_bench import Meeting, NotesBench, recorded, spoken_lines

LAUNCH = recorded("launch_sync")
LAUNCH_LINES = spoken_lines(LAUNCH)
EMPTY = '{"findings": []}'


def kept_due(meeting: Meeting, due: str) -> date | None:
    """The due date as the rules keep it for this meeting's day."""
    day = meeting.started_at.date()
    parsed = date.fromisoformat(due)
    return parsed if day <= parsed <= day + timedelta(days=366) else None


def work(meeting: Meeting, stage: Stage, source: RunSource = RunSource.LIVE) -> StageWork:
    return StageWork(meeting.scope, meeting.run_id, meeting.meeting_id, source, stage, 1)


async def test_notes_from_recorded_answers_keep_findings_with_evidence_inside_the_meeting(
    notes_bench: NotesBench,
) -> None:
    meeting = await notes_bench.meeting(LAUNCH_LINES)
    notes_bench.model.answer("window", LAUNCH["findings"])
    notes_bench.model.answer("summary", LAUNCH["summary"])

    assert await notes_bench.drive(meeting.first)

    findings = await notes_bench.findings(meeting)
    notes, record, run = await notes_bench.notes(meeting)
    by_kind = {f.kind: f for f in findings}
    assert [f.kind for f in findings] == [
        "key_point", "decision", "risk", "action_item", "promise", "question",
    ]  # fmt: skip
    for finding in findings:
        assert 0 <= finding.start_ms <= finding.end_ms <= record.seconds * 1000
    assert (by_kind["decision"].start_ms, by_kind["decision"].end_ms) == (14_000, 26_000)
    assert (by_kind["action_item"].owner_speaker, by_kind["promise"].owner_name) == (2, "Марина")
    assert by_kind["decision"].due_on == kept_due(meeting, "2026-10-28")
    assert {f.revision for f in findings} == {1}
    assert RunState(run.state) is RunState.SUCCEEDED
    assert record.notes_revision == 1
    assert notes.write_up is not None
    assert notes.map is not None
    assert (notes.write_up_template, notes.write_up_automatic) == ("enhanced", True)
    assert notes.findings_run_id == notes.write_up_run_id == meeting.run_id
    summary, key_points, decisions, actions = notes.write_up["sections"]
    assert summary["text"].startswith("Команда готовит запуск")
    assert key_points["finding_ids"] == [str(by_kind["key_point"].id)]
    assert decisions["finding_ids"] == [str(by_kind["decision"].id)]
    assert actions["finding_ids"] == [str(by_kind["action_item"].id)]
    assert notes.map["label"] == "Запуск приложения"
    assert [topic["label"] for topic in notes.map["children"]] == [
        "Запуск приложения", "Сервер уведомлений",
    ]  # fmt: skip
    [event] = await notes_bench.ready_events()
    assert (event["revision"], event["decisions"], event["promises"], event["risks"]) == (
        1,
        1,
        1,
        1,
    )
    assert await notes_bench.cost_keys() == sorted(
        [f"notes:{meeting.run_id}:findings:0", f"notes:{meeting.run_id}:write_up:0"]
    )


async def test_a_redelivered_stage_writes_nothing_twice_and_a_repeated_call_costs_one_row(
    notes_bench: NotesBench,
) -> None:
    lines = [(n % 2, n * 5, f"Реплика номер {n} о плане работ на квартал.") for n in range(24)]
    meeting = await notes_bench.meeting(lines)
    notes_bench.with_budget(900)
    notes_bench.model.answer("window", EMPTY)
    notes_bench.model.answer(
        "window",
        HTTPStatus.INTERNAL_SERVER_ERROR,
        '{"findings": [{"kind": "decision", "text": "План утверждён", "first_line": 10,'
        ' "last_line": 11}]}',
        part=2,
    )
    notes_bench.model.answer("summary", '{"summary": "План утверждён."}')

    retried = await notes_bench.drive(meeting.first)
    asked_first = len(notes_bench.model.asked)
    finished = await notes_bench.drive(meeting.first)
    stages = notes_bench.stages(900)
    calls = len(notes_bench.model.asked)
    await stages[Stage.FINDINGS].run(work(meeting, Stage.FINDINGS))
    await stages[Stage.WRITE_UP].run(work(meeting, Stage.WRITE_UP))

    windows = {asked.part or 0 for asked in notes_bench.model.of("window")}
    assert (retried, finished) == (False, True)
    assert len(windows) >= 3
    assert len(notes_bench.model.of("window")) > len(windows)
    assert calls > asked_first
    assert len(notes_bench.model.asked) == calls
    assert [f.text for f in await notes_bench.findings(meeting)] == ["План утверждён"]
    assert len(await notes_bench.ready_events()) == 1
    keys = await notes_bench.cost_keys()
    assert len(keys) == len(set(keys))
    expected = {f"notes:{meeting.run_id}:findings:{2 * (part - 1)}" for part in windows}
    assert expected | {f"notes:{meeting.run_id}:write_up:0"} == set(keys)


async def test_a_rewrite_with_another_template_keeps_the_findings_and_their_ids(
    notes_bench: NotesBench,
) -> None:
    meeting = await notes_bench.meeting(LAUNCH_LINES)
    notes_bench.model.answer("window", LAUNCH["findings"])
    notes_bench.model.answer("summary", LAUNCH["summary"], '{"summary": "Разговор о запуске."}')
    await notes_bench.drive(meeting.first)
    before = {f.id for f in await notes_bench.findings(meeting)}
    person = meeting.scope.user_id
    assert person is not None
    headers = {**bearer(Home.EU, person), "Idempotency-Key": "rewrite-1"}
    path = f"/v1/notes/{meeting.meeting_id}/write-up"

    accepted = await notes_bench.http.post(path, json={"template_id": "oneOnOne"}, headers=headers)
    again = await notes_bench.http.post(path, json={"template_id": "oneOnOne"}, headers=headers)
    reused = await notes_bench.http.post(path, json={"template_id": "teamSync"}, headers=headers)
    unknown = await notes_bench.http.post(
        path, json={"template_id": "nope"}, headers={**headers, "Idempotency-Key": "rewrite-2"}
    )
    [payload] = notes_bench.sent.payloads[-1:]
    await notes_bench.drive(payload)

    assert accepted.status_code == HTTPStatus.ACCEPTED
    assert again.json() == accepted.json()
    assert (reused.status_code, reused.json()["error"]["code"]) == (422, "idempotency_key_reused")
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (404, "template_not_found")
    assert payload.run_id == uuid.UUID(accepted.json()["run_id"]) != meeting.run_id
    assert payload.stage is Stage.WRITE_UP
    notes, record, _ = await notes_bench.notes(meeting)
    assert {f.id for f in await notes_bench.findings(meeting)} == before
    assert notes.write_up is not None
    sections = notes.write_up["sections"]
    assert [s["heading_code"] for s in sections] == ["howItsGoing", "topics", "nextSteps"]
    listed = {i for s in sections for i in s.get("finding_ids", [])}
    assert listed
    assert listed <= {str(i) for i in before}
    assert sections[0]["text"] == "Разговор о запуске."
    assert (notes.write_up_template, notes.write_up_automatic) == ("oneOnOne", False)
    assert (notes.findings_run_id, notes.write_up_run_id) == (meeting.run_id, payload.run_id)
    assert (record.template_id, record.notes_revision) == ("oneOnOne", 2)
    assert [e["revision"] for e in await notes_bench.ready_events()] == [1, 2]


async def test_an_unreadable_answer_is_asked_again_once_and_then_recorded(
    notes_bench: NotesBench,
) -> None:
    meeting = await notes_bench.meeting(LAUNCH_LINES)
    notes_bench.model.answer("window", "", "Я не нашёл ничего важного.", LAUNCH["findings"])
    notes_bench.model.answer("summary", '{"summary": ', "Встреча прошла хорошо.")

    first = await notes_bench.drive(meeting.first)
    _, _, run = await notes_bench.notes_or_run(meeting)
    second = await notes_bench.drive(meeting.first)

    windows = notes_bench.model.of("window")
    assert (first, second) == (False, True)
    assert run.stage_state["findings"]["error_code"] == "model_answer_unreadable"
    assert [asked.again for asked in windows] == [False, True, False]
    assert [role for role, _ in windows[1].messages] == ["system", "user", "user"]
    assert windows[1].messages[-1][1] == ASK_AGAIN
    summaries = notes_bench.model.of("summary")
    assert [role for role, _ in summaries[1].messages] == ["system", "user", "assistant", "user"]
    assert notes_bench.answers("window", "lost") == 1
    assert notes_bench.answers("window", "read") == 1
    assert notes_bench.answers("summary", "lost") == 1
    notes, _, run = await notes_bench.notes(meeting)
    assert notes.write_up is not None
    assert notes.write_up["sections"][0] == {
        "kind": "summary",
        "heading_code": "summary",
        "text": None,
    }
    assert RunState(run.state) is RunState.SUCCEEDED
    assert len(await notes_bench.findings(meeting)) == 6


async def test_a_meeting_over_the_budget_is_read_whole_and_its_write_up_keeps_the_closing_lines(
    notes_bench: NotesBench,
) -> None:
    lines = [
        (n % 3, n * 4, f"Это реплика {n}, она о ходе проекта и следующих шагах.") for n in range(60)
    ]
    meeting = await notes_bench.meeting(lines)
    notes_bench.with_budget(1_200)
    notes_bench.model.answer("window", EMPTY)
    notes_bench.model.answer("summary", '{"summary": "Обсудили ход проекта."}')

    assert await notes_bench.drive(meeting.first)

    shown = [rendered(line) for line in numbered([(s * 1000, 4000, w, t) for w, s, t in lines])]
    seen: set[str] = set()
    for asked in notes_bench.model.of("window"):
        header, *parts = asked.data.split("\n")
        assert header.startswith("Transcript, part ")
        assert set(parts) <= set(shown)
        seen |= set(parts)
    assert seen == set(shown)
    [summary] = notes_bench.model.of("summary")
    closing = summary.data.split("The end of the transcript:\n", 1)[1].split("\n")
    assert closing == shown[len(shown) - len(closing) :]
    assert shown[0] not in closing
    assert len(closing) > 1


async def test_a_russian_meeting_without_consent_fails_its_run_at_once(
    notes_bench: NotesBench,
) -> None:
    meeting = await notes_bench.meeting(LAUNCH_LINES, home=Home.RU)
    notes_bench.model.answer("window", LAUNCH["findings"])

    assert await notes_bench.drive(meeting.first)

    _, _, run = await notes_bench.notes_or_run(meeting)
    assert (RunState(run.state), run.error_code) == (RunState.FAILED, "consent_required")
    assert notes_bench.model.asked == []
