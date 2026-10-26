"""The OpenRouter wire format: request bodies and answers, as pure functions (no network).

Facts this module relies on, from OpenRouter's documentation read on 2026-10-13:

- usage, with `cost` in credits (USD), comes in every answer and in a stream's last chunk
- web search is the server tool `openrouter:web_search`
- generated images come in `choices[0].message.images` as data URLs
- `/embeddings` answers `data[].embedding` with its `index`
- `/rerank` answers `results[].index` and `relevance_score`, with `usage.search_units` as
  its billing unit and `usage.cost` optional

Anything else in an answer is a provider error, never a silent default.
"""

import base64
import binascii
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Final

from shosai.core.ai.adapters.http_calls import Json
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import (
    ChatMessage,
    ChatRequest,
    ImagePart,
    Role,
    TextPart,
    ToolCall,
)
from shosai.core.ai.results import Citation, Unit, Usage

DATA_URL: Final = re.compile(r"data:([\w.+-]+/[\w.+-]+);base64,(.*)", re.DOTALL)
WEB_SEARCH_TOOL: Final = "openrouter:web_search"


def data_url(image: ImagePart) -> str:
    """An image as the data URL OpenRouter takes in a message."""
    return f"data:{image.media_type};base64,{base64.b64encode(image.data).decode('ascii')}"


def message_body(message: ChatMessage) -> Json:
    """One message in OpenRouter's (OpenAI-compatible) shape."""
    parts: list[Json] = []
    for part in message.parts:
        if isinstance(part, TextPart):
            parts.append({"type": "text", "text": part.text})
        else:
            parts.append({"type": "image_url", "image_url": {"url": data_url(part)}})
    body: Json = {"role": message.role.value, "content": parts}
    if message.role is Role.TOOL:
        body["tool_call_id"] = message.tool_call_id
        body["content"] = "".join(p.text for p in message.parts if isinstance(p, TextPart))
    if message.tool_calls:
        # Сообщение модели только с вызовами: содержимого нет, не пустой список частей.
        body["content"] = body["content"] or None
        body["tool_calls"] = [
            {"id": call.call_id, "type": "function",
             "function": {"name": call.name, "arguments": call.arguments}}
            for call in message.tool_calls
        ]  # fmt: skip
    return body


def chat_body(model: str, request: ChatRequest, *, stream: bool) -> Json:
    """The body of `/chat/completions`."""
    tools: list[Json] = [
        {"type": "function",
         "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in request.tools
    ]  # fmt: skip
    if request.web_search_results:
        tools.append(
            {"type": WEB_SEARCH_TOOL, "parameters": {"max_results": request.web_search_results}}
        )
    body: Json = {
        "model": model,
        "messages": [message_body(message) for message in request.messages],
        "max_tokens": request.max_output_tokens,
        "stream": stream,
    }
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if tools:
        body["tools"] = tools
    return body


def usage_of(raw: object, *, unit: Unit | None = None, units_field: str = "") -> Usage:
    """Usage of an answer: tokens, the billing units of non-token calls and the reported cost."""
    usage = raw if isinstance(raw, dict) else {}
    details = usage.get("prompt_tokens_details") or {}
    units = Decimal(0)
    if unit is not None:
        units = Decimal(str(usage.get(units_field) or 1))
    return Usage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        cached_tokens=int(details.get("cached_tokens") or 0) if isinstance(details, dict) else 0,
        output_tokens=int(usage.get("completion_tokens") or 0),
        units=units,
        unit=unit,
        reported_cost_usd=reported_cost(usage.get("cost")),
    )


def reported_cost(raw: object) -> Decimal | None:
    """The cost the provider named, or None when it is absent or not a number."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        cost = Decimal(str(raw))
    except InvalidOperation:
        return None
    return cost if cost.is_finite() and cost >= 0 else None


def tool_calls_of(message: Json) -> tuple[ToolCall, ...]:
    """The tools the model asked to call."""
    calls = message.get("tool_calls") or []
    return tuple(
        ToolCall(
            call_id=str(call.get("id") or ""),
            name=str((call.get("function") or {}).get("name") or ""),
            arguments=str((call.get("function") or {}).get("arguments") or "{}"),
        )
        for call in calls
        if isinstance(call, dict)
    )


def citations_of(message: Json) -> tuple[Citation, ...]:
    """The web pages a web search answer cites, each once, in the order they are cited."""
    found: dict[str, Citation] = {}
    for annotation in message.get("annotations") or []:
        if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
            continue
        cited = annotation.get("url_citation") or {}
        url = str(cited.get("url") or "") if isinstance(cited, dict) else ""
        if url.startswith(("https://", "http://")) and url not in found:
            found[url] = Citation(
                url=url,
                title=str(cited.get("title") or url),
                snippet=str(cited.get("content") or ""),
            )
    return tuple(found.values())


class StreamedToolCalls:
    """The tool calls of a streamed answer, assembled from their pieces.

    A stream sends each call in pieces keyed by its index: the id and the name once, the
    arguments' JSON in fragments. The calls are whole only when the answer finishes.
    """

    def __init__(self) -> None:
        self._parts: dict[int, list[str]] = {}

    def take(self, delta: Json) -> None:
        """Add the pieces of tool calls a delta carries."""
        pieces = delta.get("tool_calls") or []
        for piece in pieces if isinstance(pieces, list) else ():
            if not isinstance(piece, dict):
                continue
            index = piece.get("index")
            slot = self._parts.setdefault(index if isinstance(index, int) else 0, ["", "", ""])
            function = piece.get("function") or {}
            slot[0] = slot[0] or str(piece.get("id") or "")
            slot[1] = slot[1] or str(function.get("name") or "")
            slot[2] += str(function.get("arguments") or "")

    def calls(self) -> tuple[ToolCall, ...]:
        """The whole calls in their order."""
        return tuple(
            ToolCall(call_id=call_id, name=name, arguments=arguments or "{}")
            for call_id, name, arguments in (self._parts[index] for index in sorted(self._parts))
        )


def first_choice(answer: Json) -> Json:
    """`choices[0]` of an answer, or a provider error."""
    choices = answer.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    return choices[0]


def image_of(message: Json) -> tuple[bytes, str]:
    """The first generated image of a message as bytes and an image media type."""
    images = message.get("images") or []
    url = None
    if isinstance(images, list) and images and isinstance(images[0], dict):
        url = (images[0].get("image_url") or {}).get("url")
    match = DATA_URL.fullmatch(url.strip()) if isinstance(url, str) else None
    # Тип приходит от провайдера и доходит до браузера: только image/*.
    if match is None or not match.group(1).lower().startswith("image/"):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except binascii.Error, ValueError:
        raise AiCallError(AiFailure.PROVIDER_ERROR) from None
    if not data:
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    return data, match.group(1).lower()


def stream_chunk(line: str) -> Json | None:
    """The JSON of one SSE line; None for comments, blank lines and the end marker."""
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        raise AiCallError(AiFailure.PROVIDER_ERROR) from None
    if not isinstance(chunk, dict) or "error" in chunk:
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    return chunk
