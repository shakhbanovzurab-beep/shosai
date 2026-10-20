"""Share links and their public page (step 13, MT-D5, MT-D12): one refusal, nothing leaked."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord
from shosai.features.meetings.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from tests.features.billing.people_bench import bearer
from tests.features.meetings.native_bench import Written, meeting
from tests.features.meetings.share_bench import ShareBench

START = datetime.now(UTC).replace(day=1, hour=1, minute=0, second=0, microsecond=0)
LINES = [(0, 0, "Hello, team."), (5_000, 1, "Let us start."), (12_000, 0, "Budget first.")]
SECTIONS: list[dict[str, Any]] = [
    {"kind": "summary", "heading_code": "summary", "text": "We agreed the budget."},
    {"kind": "action_items", "heading_code": "action_items", "finding_ids": [0]},
]
FINDINGS = [("action_item", "Send the estimate.", 13_000)]
type Json = dict[str, Any]


async def turned_on(
    bench: ShareBench, owner: uuid.UUID, meeting_id: uuid.UUID, **settings: bool | str
) -> Json:
    answer = await bench.http.put(
        f"/v1/meetings/{meeting_id}/share-link", json=settings, headers=bearer((Home.EU, owner))
    )
    assert answer.status_code == 200, answer.text
    link: Json = answer.json()["link"]
    return link


def without_request(answer: httpx.Response) -> tuple[int, Json]:
    """The answer's status and body, the request's own id left out."""
    body: Json = answer.json()
    body["error"].pop("request_id", None)
    return answer.status_code, body


async def test_a_link_is_turned_on_changed_and_off_and_the_next_has_a_new_token(
    share_bench: ShareBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    meeting_id = await meeting(share_bench.homes, owner, ("Budget", START), Written(LINES))
    headers = bearer((Home.EU, owner))
    url = f"/v1/meetings/{meeting_id}/share-link"

    first = await turned_on(share_bench, owner, meeting_id, expiry="7d", allow_comments=True)
    changed = await turned_on(share_bench, owner, meeting_id, expiry="7d", show_names=True)
    share_bench.clock.advance(timedelta(days=1))
    recounted = await turned_on(share_bench, owner, meeting_id, expiry="30d", allow_comments=True)
    await share_bench.http.post(f"/v1/shared/{first['token']}/comments", json={"text": "Thanks!"})
    off = await share_bench.http.delete(url, headers=headers)
    after = await share_bench.http.get(url, headers=headers)
    old = await share_bench.http.get(f"/v1/shared/{first['token']}")
    again = await turned_on(share_bench, owner, meeting_id)
    foreign = await share_bench.http.get(url, headers=bearer((Home.EU, stranger)))

    async with share_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        comments = await session.scalar(select(func.count()).select_from(ShareCommentRecord))
    assert first["path"] == f"/s/{first['token']}"
    assert (changed["token"], changed["expires_at"]) == (first["token"], first["expires_at"])
    assert recounted["token"] == first["token"]
    assert recounted["expires_at"] > first["expires_at"]
    assert (off.status_code, after.json(), comments) == (204, {"link": None}, 0)
    assert old.status_code == 404
    assert again["token"] != first["token"]
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "meeting_not_found")


async def test_every_link_that_does_not_open_answers_the_same(share_bench: ShareBench) -> None:
    owner, hidden_owner = uuid.uuid4(), uuid.uuid4()
    expiring = await meeting(share_bench.homes, owner, ("Soon", START))
    deleted = await meeting(share_bench.homes, owner, ("Gone", START))
    unkept = await meeting(share_bench.homes, owner, ("Private", START), state=("active", False))
    away = await meeting(share_bench.homes, hidden_owner, ("Away", START))
    tokens = {
        "expired": (await turned_on(share_bench, owner, expiring, expiry="7d"))["token"],
        "hidden": (await turned_on(share_bench, owner, deleted))["token"],
        "away": (await turned_on(share_bench, hidden_owner, away))["token"],
    }
    async with share_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add(ShareLinkRecord(session_id=unkept, user_id=owner, token="draft-unkept_1"))
        hidden = await session.get(MeetingRecord, deleted)
        assert hidden is not None
        hidden.deleted_at = share_bench.clock.now
    async with share_bench.homes.transactions.begin(TenancyScope(Home.EU, hidden_owner)) as s:
        s.add(SettingsRecord(user_id=hidden_owner, account_hidden=True))
    share_bench.clock.advance(timedelta(days=8))
    unknown = "x" * 43

    answers = [
        await share_bench.http.get(f"/v1/shared/{token}")
        for token in [*tokens.values(), "draft-unkept_1", unknown, "not a token!"]
    ]

    assert {json.dumps(without_request(a), sort_keys=True) for a in answers} == {
        json.dumps(
            (404, {"error": {"code": "share_not_found"}, "detail": "share_not_found"}),
            sort_keys=True,
        )
    }


async def test_names_hidden_never_leak_a_name_or_an_address(share_bench: ShareBench) -> None:
    owner = uuid.uuid4()
    share_bench.people.by_person[owner] = ("Мария Соколова", "ru")
    findings = [("action_item", "Send the estimate.", 13_000)]
    meeting_id = await meeting(
        share_bench.homes,
        owner,
        ("Budget", START),
        Written(LINES, write_up=("enhanced", SECTIONS, findings)),
    )
    await share_bench.participants(
        owner, meeting_id, [("Anna Smith", "anna@example.com"), ("bob@corp.com", None)]
    )

    hidden = await turned_on(share_bench, owner, meeting_id, show_names=False)
    page = (await share_bench.http.get(f"/v1/shared/{hidden['token']}")).json()
    await turned_on(share_bench, owner, meeting_id, show_names=True)
    named = (await share_bench.http.get(f"/v1/shared/{hidden['token']}")).json()

    text = json.dumps(page, ensure_ascii=False)
    assert "Anna" not in text
    assert "Мария" not in text
    assert "@" not in text
    assert (page["participants"], page["participant_count"]) == (None, 2)
    assert [(line["speaker"], line["speaker_name"]) for line in page["transcript"]] == [
        (1, None), (2, None), (1, None),
    ]  # fmt: skip
    assert page["sections"][1]["items"][0]["owner_name"] is None
    assert "@" not in json.dumps(named, ensure_ascii=False)
    assert named["participants"] == ["Anna Smith"]
    assert [line["speaker_name"] for line in named["transcript"]] == [
        "Мария Соколова",
        None,
        "Мария Соколова",
    ]
    assert named["sections"][0] == {
        "kind": "summary", "heading_code": "summary", "title": None,
        "text": "We agreed the budget.", "items": None,
    }  # fmt: skip


async def test_a_hidden_transcript_and_closed_comments(share_bench: ShareBench) -> None:
    owner = uuid.uuid4()
    meeting_id = await meeting(share_bench.homes, owner, ("Budget", START), Written(LINES))
    link = await turned_on(share_bench, owner, meeting_id, show_transcript=False)
    page = (await share_bench.http.get(f"/v1/shared/{link['token']}")).json()
    closed = await share_bench.http.post(
        f"/v1/shared/{link['token']}/comments", json={"text": "Hi"}
    )
    listed = await share_bench.http.get(f"/v1/shared/{link['token']}/comments")

    assert (page["transcript"], page["transcript_truncated"], page["allow_comments"]) == (
        None,
        False,
        False,
    )
    assert [(a.status_code, a.json()["error"]["code"]) for a in (closed, listed)] == [
        (409, "comments_closed")
    ] * 2


async def test_comments_keep_a_name_or_a_guest_and_six_a_minute(share_bench: ShareBench) -> None:
    owner = uuid.uuid4()
    meeting_id = await meeting(share_bench.homes, owner, ("Budget", START), Written(LINES))
    token = (await turned_on(share_bench, owner, meeting_id, allow_comments=True))["token"]
    url = f"/v1/shared/{token}/comments"

    named = await share_bench.http.post(
        url, json={"author": "  Ivan   Petrov ", "text": " Thanks! "}
    )
    share_bench.clock.advance(timedelta(seconds=1))
    guest = await share_bench.http.post(url, json={"text": "Me too."})
    invalid = await share_bench.http.post(url, json={"author": "x" * 61, "text": "Hi"})
    rest = [await share_bench.http.post(url, json={"text": f"Note {n}"}) for n in range(4)]
    listed = (await share_bench.http.get(url)).json()["items"]

    assert (named.status_code, named.json()["author"], named.json()["text"]) == (
        201,
        "Ivan Petrov",
        "Thanks!",
    )
    assert guest.json()["author"] is None
    assert (invalid.status_code, invalid.json()["error"]["code"]) == (422, "comment_invalid")
    # Шесть запросов в минуту с адреса, отклонённый тоже: седьмой получает 429.
    assert [a.status_code for a in rest] == [201, 201, 201, 429]
    assert [c["text"] for c in listed] == ["Thanks!", "Me too.", "Note 0", "Note 1", "Note 2"]


async def test_a_link_resolves_from_its_own_home_and_a_draft_token_still_opens(
    share_bench: ShareBench,
) -> None:
    owner = uuid.uuid4()
    eu = await meeting(share_bench.homes, owner, ("EU meeting", START))
    eu_token = (await turned_on(share_bench, owner, eu))["token"]
    ru = uuid.uuid4()
    async with share_bench.homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        session.add(
            MeetingRecord(
                id=ru, user_id=owner, title="RU meeting", status="completed", started_at=START,
                ended_at=START + timedelta(minutes=30), seconds=1800,
            )
        )  # fmt: skip
        await session.flush()
        session.add(ShareLinkRecord(session_id=ru, user_id=owner, token="Dr4ft_tok-en"))

    from_eu = await share_bench.http.get(f"/v1/shared/{eu_token}")
    from_ru = await share_bench.http.get("/v1/shared/Dr4ft_tok-en")

    assert (from_eu.status_code, from_eu.json()["title"]) == (200, "EU meeting")
    assert (from_ru.status_code, from_ru.json()["title"]) == (200, "RU meeting")
