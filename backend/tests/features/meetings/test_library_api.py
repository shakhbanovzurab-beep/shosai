"""The cabinet's library and a meeting's page in the cabinet's shapes (meetings step 7a)."""

import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from shosai.features.meetings.application.meeting_content import FINDINGS_CURSOR, FindingPosition
from tests.features.meetings.library_bench import LibraryBench, MeetingSeed, Notes, bearer

NOW = datetime.now(UTC)
FINDINGS = (
    ("key_point", "Сборка готова"), ("decision", "Запуск 28 октября"),
    ("key_point", "Ревью идёт"), ("action_item", "Провести тест"),
    ("key_point", "Нужен пресс-релиз"), ("key_point", "Цены не решены"),
    ("action_item", "Написать пресс-релиз"), ("decision", "Цены — на следующей неделе"),
)  # fmt: skip
PEOPLE = (*((f"Участник {n}", f"p{n}@example.com") for n in range(5)), (None, "anna@x.io"))


def full(owner: uuid.UUID, started: datetime) -> MeetingSeed:
    return MeetingSeed(
        owner=owner, title="Запуск", started_at=started, participants=PEOPLE,
        lines=[(0, 0, "Начнём."), (1, 5, "Сборка готова."), (None, 9, "Хорошо."), (0, 14, "Итак.")],
        speakers=[(0, "owner", 9000), (1, "other", 4000)],
        notes=Notes(
            findings=FINDINGS,
            map_topics=[("Запуск", ["Сборка готова", "Ревью идёт"]), ("Цены", ["Не решены"])],
        ),
    )  # fmt: skip


async def test_the_library_pages_newest_first_with_what_its_cards_show(
    library_bench: LibraryBench,
) -> None:
    owner = uuid.uuid4()
    ready = await library_bench.seed(full(owner, NOW - timedelta(hours=3)))
    working = await library_bench.seed(
        MeetingSeed(owner, title="Идёт обработка", started_at=NOW - timedelta(hours=2),
                    run_state="running")
    )  # fmt: skip
    failed = await library_bench.seed(
        MeetingSeed(owner, started_at=NOW - timedelta(hours=1), run_state="failed")
    )

    first = (await library_bench.get(owner, "/v1/meetings", limit=2)).json()
    second = (
        await library_bench.get(owner, "/v1/meetings", limit=2, cursor=first["next_cursor"])
    ).json()
    foreign = FINDINGS_CURSOR.encode(FindingPosition(position=1))
    refused = await library_bench.get(owner, "/v1/meetings", cursor=foreign)
    too_many = await library_bench.get(owner, "/v1/meetings", limit=101)

    assert [i["id"] for i in first["items"]] == [str(failed.meeting_id), str(working.meeting_id)]
    assert [i["notes"] for i in first["items"]] == ["failed", "processing"]
    assert second["next_cursor"] is None
    [card] = second["items"]
    assert card == {
        "id": str(ready.meeting_id), "title": "Запуск", "status": "completed", "source": "live",
        "started_at": card["started_at"], "ended_at": card["ended_at"], "seconds": 1800,
        "owned": True, "folder_id": None,
        "participant_names": ["Участник 0", "Участник 1", "Участник 2", "Участник 3", "Участник 4"],
        "participant_count": 6, "summary": "Обсудили запуск.",
        "key_points": ["Сборка готова", "Ревью идёт", "Нужен пресс-релиз"],
        "first_decision": "Запуск 28 октября", "action_items": 2, "notes": "ready",
    }  # fmt: skip
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "invalid_cursor")
    assert too_many.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_the_owner_files_and_renames_and_a_reader_may_only_read(
    library_bench: LibraryBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    folder = await library_bench.folder(owner)
    theirs = await library_bench.folder(stranger)
    filed = await library_bench.seed(MeetingSeed(owner, title="В папке", folder_id=folder))
    loose = await library_bench.seed(MeetingSeed(owner, title="Без папки"))
    path = f"/v1/meetings/{loose.meeting_id}"

    moved = await library_bench.http.patch(
        path, json={"folder_id": str(folder), "title": " Новое имя "}, headers=bearer(owner)
    )
    in_folder = await library_bench.every(owner, "/v1/meetings", folder=str(folder))
    out = await library_bench.http.patch(path, json={"folder_id": None}, headers=bearer(owner))
    unfiled = await library_bench.every(owner, "/v1/meetings", folder="none")
    foreign = await library_bench.http.patch(
        path, json={"folder_id": str(theirs)}, headers=bearer(owner)
    )
    blank = await library_bench.http.patch(path, json={"title": "   "}, headers=bearer(owner))
    hidden = await library_bench.http.patch(path, json={"title": "Чужое"}, headers=bearer(stranger))
    bad_filter = await library_bench.get(owner, "/v1/meetings", folder="somewhere")

    assert moved.status_code == HTTPStatus.OK
    assert (moved.json()["title"], moved.json()["folder_id"]) == ("Новое имя", str(folder))
    assert {i["id"] for i in in_folder} == {str(filed.meeting_id), str(loose.meeting_id)}
    assert out.json()["folder_id"] is None
    assert [i["id"] for i in unfiled] == [str(loose.meeting_id)]
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "folder_not_found")
    assert (blank.status_code, blank.json()["error"]["code"]) == (422, "title_empty")
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "meeting_not_found")
    assert bad_filter.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_a_meeting_s_page_and_content_come_in_the_cabinet_s_shapes(
    library_bench: LibraryBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await library_bench.seed(full(owner, NOW - timedelta(hours=1)))
    bare = await library_bench.seed(MeetingSeed(owner, title="Без заметок", run_state="failed"))
    base = f"/v1/meetings/{meeting.meeting_id}"

    page = (await library_bench.get(owner, base)).json()
    lines = await library_bench.every(owner, f"{base}/transcript", limit=3)
    first_lines = (await library_bench.get(owner, f"{base}/transcript", limit=3)).json()
    write_up = (await library_bench.get(owner, f"{base}/write-up")).json()
    decisions = await library_bench.every(owner, f"{base}/findings", kind="decision", limit=1)
    nodes = await library_bench.every(owner, f"{base}/map", limit=2)
    oversized = await library_bench.get(owner, f"{base}/transcript", limit=501)
    no_write_up = await library_bench.get(owner, f"/v1/meetings/{bare.meeting_id}/write-up")
    no_map = await library_bench.get(owner, f"/v1/meetings/{bare.meeting_id}/map")
    no_findings = await library_bench.every(owner, f"/v1/meetings/{bare.meeting_id}/findings")

    assert (page["manageable"], page["revision"], page["line_count"]) == (True, 1, 4)
    assert page["run_id"] == str(meeting.run_id)
    assert page["participants"][5] == {
        "id": page["participants"][5]["id"], "name": None, "email": "anna@x.io", "source": "added",
    }  # fmt: skip
    assert page["speakers"] == [
        {"idx": 0, "role": "owner", "talk_ms": 9000},
        {"idx": 1, "role": "other", "talk_ms": 4000},
    ]
    assert [line["text"] for line in lines] == ["Начнём.", "Сборка готова.", "Хорошо.", "Итак."]
    assert lines[2] == {
        "seq": 3,
        "start_ms": 9000,
        "duration_ms": 900,
        "speaker": None,
        "text": "Хорошо.",
    }
    assert first_lines["next_cursor"] is not None
    summary, key_points, decided, actions = write_up["sections"]
    assert (write_up["template_id"], write_up["revision"]) == ("enhanced", 1)
    assert summary == {
        "kind": "summary", "heading_code": "summary", "title": None,
        "text": "Обсудили запуск.", "items": None,
    }  # fmt: skip
    assert [i["text"] for i in key_points["items"]] == [
        "Сборка готова", "Ревью идёт", "Нужен пресс-релиз", "Цены не решены",
    ]  # fmt: skip
    assert decided["items"][0].keys() == {
        "id", "kind", "text", "topic", "owner_speaker", "owner_name", "due_on", "start_ms",
        "end_ms", "quote",
    }  # fmt: skip
    assert [i["text"] for i in actions["items"]] == ["Провести тест", "Написать пресс-релиз"]
    assert [d["text"] for d in decisions] == ["Запуск 28 октября", "Цены — на следующей неделе"]
    assert nodes == [
        {"id": "0", "parent_id": None, "depth": 0, "label": "Запуск"},
        {"id": "1", "parent_id": "0", "depth": 1, "label": "Запуск"},
        {"id": "2", "parent_id": "1", "depth": 2, "label": "Сборка готова"},
        {"id": "3", "parent_id": "1", "depth": 2, "label": "Ревью идёт"},
        {"id": "4", "parent_id": "0", "depth": 1, "label": "Цены"},
        {"id": "5", "parent_id": "4", "depth": 2, "label": "Не решены"},
    ]
    assert oversized.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (no_write_up.status_code, no_write_up.json()["error"]["code"]) == (
        404, "write_up_not_found",
    )  # fmt: skip
    assert no_map.json()["error"]["code"] == "map_not_found"
    assert no_findings == []
