"""Leo in the admin panel (ADR 0068 AG-D5; agent step 16a): the platform operator's threads and
turns behind the admin's session, answered in Russian under the operator's policy, paid by the
platform's `admin_assistant` account, offered the `platform` toolset alone — which no person is
ever offered — and kept apart from every person's threads."""

import uuid
from typing import Final

import httpx

from shosai.core.ai.calls import PlatformAccount
from shosai.core.ai.requests import ChatRequest
from shosai.features.agent.domain.operator import OPERATOR_ID
from shosai.features.agent.infrastructure.prompts import OPERATOR_POLICY
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.features.agent.turn_doubles import ADMIN_SESSION
from tests.features.billing.people_bench import bearer

ADMIN: Final = "/v1/admin/agent"
PAGE: Final = "/admin/ai-models"
COOKIE: Final = {"Cookie": f"shosai_admin={ADMIN_SESSION}"}


async def operator_thread(http: httpx.AsyncClient) -> str:
    made = await http.post(
        f"{ADMIN}/threads", json={"scope": {"kind": "personal"}},
        headers={"Idempotency-Key": uuid.uuid4().hex} | COOKIE,
    )  # fmt: skip
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def operator_asks(
    http: httpx.AsyncClient, thread: str, text: str, extra: dict[str, object] | None = None
) -> httpx.Response:
    return await http.post(
        f"{ADMIN}/threads/{thread}/turns",
        json={"text": text, "locale": "ru", "surface": {"path": PAGE}} | (extra or {}),
        headers={"Idempotency-Key": uuid.uuid4().hex} | COOKIE,
    )  # fmt: skip


def offered(request: ChatRequest) -> set[str]:
    return {tool.name for tool in request.tools}


async def test_the_admin_s_routes_open_to_the_admin_s_session_only(turn_bench: TurnBench) -> None:
    http = turn_bench.http
    person = bearer((HOME, uuid.uuid4()))

    anonymous = await http.get(f"{ADMIN}/threads", params={"scope": "personal"})
    with_token = await http.get(f"{ADMIN}/threads", params={"scope": "personal"}, headers=person)
    wrong = await http.get(
        f"{ADMIN}/threads", params={"scope": "personal"}, headers={"Cookie": "shosai_admin=stale"}
    )
    admin_at_person = await http.get(
        "/v1/agent/threads", params={"scope": "personal"}, headers=COOKIE
    )

    assert [r.status_code for r in (anonymous, with_token, wrong, admin_at_person)] == [
        401, 401, 401, 401,
    ]  # fmt: skip
    assert anonymous.json()["detail"] == "admin_sign_in_required"


async def test_the_operator_s_turn_is_the_platform_s_in_russian_with_platform_tools(
    turn_bench: TurnBench,
) -> None:
    thread = await operator_thread(turn_bench.http)
    turn_bench.model.scripts = [
        calling(("platform__probe", '{"query": "spend"}')),
        saying("Готово."),
    ]

    events = stream_of(await operator_asks(turn_bench.http, thread, "Сколько потратили?"))

    first = turn_bench.model.calls[0]
    assert offered(first) == {"platform__probe", "core__read_result"}
    head = "".join(getattr(part, "text", "") for part in first.messages[0].parts)
    assert head.startswith(OPERATOR_POLICY)
    assert "ru (Русский)" in head
    contexts = turn_bench.model.contexts
    assert {(c.scope, c.platform_account) for c in contexts} == {
        (None, PlatformAccount.ADMIN_ASSISTANT)
    }
    assert turn_bench.tools.ran == ["archive"]
    assert events[-1][0] == "run.completed"
    rows = await turn_bench.http.get(
        f"{ADMIN}/threads", params={"scope": "personal"}, headers=COOKIE
    )
    assert [t["id"] for t in rows.json()["items"]] == [thread]


async def test_a_person_is_never_offered_the_platform_toolset(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling(("platform__probe", '{"query": "spend"}')), saying("No.")]

    await turn_bench.ask(person, thread, "How much did the platform spend?")
    listed = await turn_bench.http.get(
        f"{ADMIN}/threads", params={"scope": "personal"}, headers=COOKIE
    )

    assert not any(name.startswith("platform__") for name in offered(turn_bench.model.calls[0]))
    assert turn_bench.tools.ran == []
    assert turn_bench.model.contexts[0].scope is not None
    assert turn_bench.model.contexts[0].scope.user_id == person
    assert listed.json()["items"] == []


async def test_the_operator_s_turn_takes_no_attachments(turn_bench: TurnBench) -> None:
    thread = await operator_thread(turn_bench.http)

    refused = await operator_asks(
        turn_bench.http, thread, "Посмотри файл", {"upload_ids": [str(uuid.uuid4())]}
    )

    assert (refused.status_code, refused.json()["detail"]) == (422, "attachments_not_allowed")
    assert OPERATOR_ID not in {c.scope.user_id for c in turn_bench.model.contexts if c.scope}
