"""The native model proxy as macOS and Windows 1.4.5 read it (agent step 14): the draft's
stream byte for byte, the clients' own request bodies, every refusal before the stream with a
`detail` string, a failure after the first byte as a short note in the person's language, and
an answer read to its end when the client has left."""

import asyncio
import base64
import json
import uuid

from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ImagePart, Role, TextPart
from shosai.core.ai.results import ChatDelta
from shosai.core.kernel.homes import Home
from shosai.features.agent.application.proxy_requests import ChatAsk
from shosai.features.agent.domain.proxy_input import Said
from shosai.features.agent.infrastructure.prompts import PROXY_RESPONSES, VISION_TASK
from shosai.features.billing.contracts import TokenRoute
from shosai.features.identity.contracts import Principal
from tests.features.agent.proxy_bench import (
    CHAT,
    MACOS,
    MODEL,
    PNG,
    VISION,
    WINDOWS,
    ProxyBench,
    profiles_of,
)
from tests.features.agent.turn_bench import HOME
from tests.features.billing.people_bench import bearer


async def test_the_stream_is_the_draft_s_byte_for_byte(proxy_bench: ProxyBench) -> None:
    person = uuid.uuid4()

    answer = await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, person)))

    assert answer.status_code == 200
    assert answer.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert (answer.headers["x-model"], answer.headers["cache-control"]) == (
        "probe/answering", "no-cache",
    )  # fmt: skip
    assert answer.headers["x-accel-buffering"] == "no"
    assert answer.content.decode() == (
        'data: {"choices": [{"delta": {"content": "Hel"}, "finish_reason": null}]}\n\n'
        'data: {"choices": [{"delta": {"content": "lo\\u2028there"}, "finish_reason": null}]}\n\n'
        'data: {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]}\n\n'
        "data: [DONE]\n\n"
    )


async def test_the_clients_bodies_reach_the_model_under_the_proxy_s_rules(
    proxy_bench: ProxyBench,
) -> None:
    person = uuid.uuid4()
    proxy_bench.turns.terms.consenting.add(person)

    mac = await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, person)))
    win = await proxy_bench.http.post(CHAT, json=WINDOWS, headers=bearer((Home.RU, person)))

    assert (mac.status_code, win.status_code) == (200, 200)
    sent = proxy_bench.model.calls
    assert [m.role for m in sent[0].messages] == [Role.SYSTEM, Role.SYSTEM, Role.USER]
    assert sent[0].messages[0].parts == (TextPart(PROXY_RESPONSES),)
    assert "(English)" in str(sent[0].messages[1].parts[0])
    assert sent[1].messages[-1].parts == (TextPart("Цена?"),)
    assert (sent[1].max_output_tokens, sent[1].temperature) == (4096, None)


async def test_every_refusal_comes_before_the_stream_with_a_detail_string(
    proxy_bench: ProxyBench,
) -> None:
    person, stranger = uuid.uuid4(), uuid.uuid4()
    post = proxy_bench.http.post

    unsigned = await post(CHAT, json=MACOS)
    no_consent = await post(CHAT, json=MACOS, headers=bearer((Home.RU, stranger)))
    other_role = await post(CHAT, json=MACOS | {"role": "coding"}, headers=bearer((HOME, person)))
    empty = await post(CHAT, json={"messages": []}, headers=bearer((HOME, person)))
    no_image = await post(VISION, json={"images": ["%%%"]}, headers=bearer((HOME, person)))
    proxy_bench.turns.terms.route = TokenRoute.STOP
    spent = await post(CHAT, json=MACOS, headers=bearer((HOME, person)))

    assert [(r.status_code, r.json()["detail"]) for r in (
        unsigned, no_consent, other_role, empty, no_image, spent,
    )] == [
        (401, "Missing Bearer token"), (403, "consent_required"), (400, "role_not_supported"),
        (400, "conversation_empty"), (400, "no_valid_image"), (402, "token_limit"),
    ]  # fmt: skip
    assert proxy_bench.model.calls == []


async def test_a_refusal_of_the_port_before_the_first_piece_is_the_status(
    proxy_bench: ProxyBench,
) -> None:
    proxy_bench.model.failure = AiCallError(AiFailure.RATE_LIMITED, retryable=True)
    proxy_bench.model.fail_at_once = True

    answer = await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, uuid.uuid4())))

    assert (answer.status_code, answer.json()["detail"]) == (429, "rate_limited")


async def test_a_failure_after_the_first_byte_ends_with_a_note_in_the_person_s_language(
    proxy_bench: ProxyBench,
) -> None:
    person = uuid.uuid4()
    profiles_of(proxy_bench).languages[person] = "ru"
    proxy_bench.model.pieces = [ChatDelta(text="Сейчас", model=MODEL)]
    proxy_bench.model.failure = AiCallError(AiFailure.PROVIDER_ERROR)

    answer = await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, person)))

    events = [line for line in answer.content.decode().split("\n\n") if line]
    assert answer.status_code == 200
    assert json.loads(events[1].removeprefix("data: ")) == {
        "choices": [
            {
                "delta": {"content": "\n[Ответ прервался. Попробуйте снова.]"},
                "finish_reason": "error",
            }
        ]
    }
    assert events[-1] == "data: [DONE]"


async def test_past_the_limit_a_person_waits(proxy_bench: ProxyBench) -> None:
    person = uuid.uuid4()
    answers = [
        await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, person)))
        for _ in range(4)
    ]

    assert [a.status_code for a in answers] == [200, 200, 200, 429]
    assert answers[-1].json()["detail"] == "rate_limited"
    assert "retry-after" in answers[-1].headers


async def test_screenshots_go_with_the_question_or_the_proxy_s_task(
    proxy_bench: ProxyBench,
) -> None:
    person = uuid.uuid4()
    frame = base64.b64encode(PNG).decode()
    body = {"images": [frame, f"data:image/png;base64,{frame}"], "prompt": "", "use_kb": False}

    first = await proxy_bench.http.post(VISION, json=body, headers=bearer((HOME, person)))
    asked = await proxy_bench.http.post(
        VISION, json={"image_base64": frame, "prompt": "What is 2+2?"},
        headers=bearer((HOME, person)),
    )  # fmt: skip

    assert (first.status_code, asked.status_code) == (200, 200)
    shots, question = (call.messages[-1].parts for call in proxy_bench.model.calls)
    assert shots[0] == TextPart(VISION_TASK)
    assert [p.media_type for p in shots[1:] if isinstance(p, ImagePart)] == ["image/png"] * 2
    assert "2 screenshots" in str(proxy_bench.model.calls[0].messages[0].parts[0])
    assert question[0] == TextPart("What is 2+2?")


async def test_an_answer_is_read_to_its_end_when_the_client_has_left(
    proxy_bench: ProxyBench,
) -> None:
    model = proxy_bench.model
    model.gate.clear()
    who = Principal(uuid.uuid4(), HOME, token_version=0)

    answer = await proxy_bench.proxy.chat(who, ChatAsk((Said("user", "Hi?"),)))
    pieces = answer.pieces()
    first = await anext(pieces)
    await pieces.aclose()
    model.gate.set()
    for _ in range(50):
        if model.drained:
            break
        await asyncio.sleep(0.01)

    assert first.text == "Hel"
    assert model.drained
