"""The native model proxy over HTTP: `POST /v1/ai/chat/stream` and `POST /v1/ai/vision/analyze`
(class `native`, contracts/; agent step 14).

The request bodies are the draft's: unknown keys are ignored, `temperature` and `max_tokens`
may be null, a conversation's first message may be an empty system one, and screenshots come
as base64 with or without a `data:` prefix (`images`, or the older `image_base64`). The answer
is the draft's stream byte for byte, which the shipped parsers read line by line: each event
`data: <JSON>` and a blank line, the JSON with a space after `,` and `:` and its text as UTF-8
— save U+2028, U+2029 and U+0085, escaped, since macOS breaks lines on them — the text under
`choices[0].delta.content`, a separate event with the finish (`stop`, `length`; `error` after
a failure, its text a short note in the person's language), then `data: [DONE]`; a comment
every 15 s while the model is silent. Every refusal comes before the stream, with `detail` the
code as a string, which both apps show; a 401 makes Windows refresh its token and retry once.
`role` is `responses`, the only one before studio (AG-D4); `use_kb` is accepted and searched
once knowledge is (step 19).
"""

import asyncio
import json
from collections.abc import AsyncIterable
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.native_proxy import NativeProxy, ProxyAnswer
from shosai.features.agent.application.proxy_requests import ChatAsk, VisionAsk
from shosai.features.agent.application.proxy_studio import PROXY_ROLES
from shosai.features.agent.domain.proxy_input import Said, frames
from shosai.features.identity.contracts import Principal, bearer_principal

RESPONSES: Final = "responses"
DONE: Final = "[DONE]"
MAX_MESSAGES: Final = 500
MAX_TOKENS: Final = 32_768
# Разрывы строк, на которых делит текст `bytes.lines` macOS: в JSON они уходят экранированными.
LINE_BREAKS: Final = str.maketrans({" ": "\\u2028", " ": "\\u2029", "\u0085": "\\u0085"})


class ProxyMessageIn(BaseModel):
    """One message of the conversation as the client keeps it."""

    role: str = Field(pattern="^(system|user|assistant)$", description="Who said it.")
    content: str = Field(description="What was said; an empty system message is ignored.")


class ProxyChatRequest(BaseModel):
    """A live conversation to answer briefly."""

    role: str = Field(
        default=RESPONSES,
        description="responses (live answers), coding or system_design — a Studio role each.",
    )
    messages: list[ProxyMessageIn] = Field(max_length=MAX_MESSAGES)
    temperature: float | None = Field(default=None, description="Held to 0–2.")
    max_tokens: int | None = Field(
        default=None, ge=1, le=MAX_TOKENS, description="At most 4096 are used."
    )
    use_kb: bool = Field(default=False, description="Accepted; searched once knowledge is.")


class ProxyVisionRequest(BaseModel):
    """Screenshots of a task, with the person's question or without one."""

    image_base64: str = Field(default="", description="One screenshot, the older field.")
    images: list[str] | None = Field(
        default=None, description="Screenshots as base64; the first six that decode are read."
    )
    prompt: str = Field(default="", description="The question; empty asks to solve the task.")
    use_kb: bool = Field(default=False, description="Accepted; searched once knowledge is.")


def chunk(text: str, finish: str | None) -> str:
    """One event's JSON, as the draft wrote it."""
    body = json.dumps({"choices": [{"delta": {"content": text}, "finish_reason": finish}]},
                      ensure_ascii=False)  # fmt: skip
    return body.translate(LINE_BREAKS)


async def events_of(answer: ProxyAnswer) -> AsyncIterable[ServerSentEvent]:
    """The answer's events, then the end marker."""
    async for piece in answer.pieces():
        yield ServerSentEvent(raw_data=chunk(piece.text, piece.finish))
    yield ServerSentEvent(raw_data=DONE)


def build_native_proxy_router(proxy: NativeProxy, ports: PortDirectory) -> APIRouter:
    """The two routes of the shipped clients' model proxy."""
    router = APIRouter(prefix="/v1/ai", tags=["native"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    async def chat_answer(
        body: ProxyChatRequest, principal: person, response: Response
    ) -> ProxyAnswer:
        role = PROXY_ROLES.get(body.role)
        if role is None:
            raise AppError("role_not_supported", HTTPStatus.BAD_REQUEST)
        ask = ChatAsk(
            tuple(Said(message.role, message.content) for message in body.messages),
            body.temperature,
            body.max_tokens,
        )
        answer = await proxy.chat(principal, ask, role)
        response.headers["X-Model"] = answer.model
        return answer

    async def vision_answer(
        body: ProxyVisionRequest, principal: person, response: Response
    ) -> ProxyAnswer:
        # Разбор до шести кадров по 8 МиБ — работа процессора: в поток, не в цикл событий.
        found = await asyncio.to_thread(frames, body.images, body.image_base64)
        ask = VisionAsk(tuple(found), body.prompt)
        answer = await proxy.vision(principal, ask)
        response.headers["X-Model"] = answer.model
        return answer

    @router.post("/chat/stream", response_class=EventSourceResponse)
    async def chat_stream(
        answer: Annotated[ProxyAnswer, Depends(chat_answer)],
    ) -> AsyncIterable[ServerSentEvent]:
        """Answer a live conversation briefly, as a stream of OpenAI-style chunks."""
        async for event in events_of(answer):
            yield event

    @router.post("/vision/analyze", response_class=EventSourceResponse)
    async def vision_analyze(
        answer: Annotated[ProxyAnswer, Depends(vision_answer)],
    ) -> AsyncIterable[ServerSentEvent]:
        """Solve the task on screenshots, as a stream of OpenAI-style chunks."""
        async for event in events_of(answer):
            yield event

    return router
