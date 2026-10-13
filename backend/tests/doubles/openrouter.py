"""OpenRouter as a transport double: scripted answers per path, every request recorded.

Slices and core test the real adapter against it, with no network: `ScriptedOpenRouter`
plays OpenRouter's side of HTTP, so the request bodies and the answer parsing are both
exercised. Answers are queued per path and served in order.
"""

import base64
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx

from shosai.core.ai.adapters.openrouter import OPENROUTER_API

type Json = dict[str, Any]


@dataclass
class ScriptedOpenRouter:
    """Queued answers by path; the requests it received, with their JSON bodies."""

    answers: dict[str, list[httpx.Response]] = field(default_factory=lambda: defaultdict(list))
    requests: list[tuple[str, Json]] = field(default_factory=list)

    def answer(self, path: str, response: httpx.Response) -> None:
        """Queue the next answer for a path such as `chat/completions`."""
        self.answers[path].append(response)

    def client(self) -> httpx.AsyncClient:
        """An HTTPX client whose transport is this double."""
        return httpx.AsyncClient(
            base_url=OPENROUTER_API + "/", transport=httpx.MockTransport(self._handle)
        )

    def bodies(self, path: str) -> list[Json]:
        """The JSON bodies sent to a path, in order."""
        return [body for sent, body in self.requests if sent == path]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1/")
        self.requests.append((path, json.loads(request.content or b"{}")))
        queued = self.answers.get(path)
        if not queued:
            return httpx.Response(500, json={"error": {"message": f"no scripted answer: {path}"}})
        return queued.pop(0)


def usage(prompt: int = 0, completion: int = 0, cached: int = 0, cost: float | None = None) -> Json:
    """A usage object as OpenRouter returns it."""
    body: Json = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "prompt_tokens_details": {"cached_tokens": cached},
    }
    if cost is not None:
        body["cost"] = cost
    return body


def chat_answer(text: str, used: Json, *, tool_calls: list[Json] | None = None) -> httpx.Response:
    """A non-streamed chat answer."""
    message: Json = {"role": "assistant", "content": text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return httpx.Response(
        200,
        json={"choices": [{"message": message, "finish_reason": "stop"}], "usage": used},
    )


def stream_answer(pieces: list[str], used: Json) -> httpx.Response:
    """A streamed answer: a comment, the pieces, a final chunk with usage, the end marker."""
    lines = [": OPENROUTER PROCESSING", ""]
    for piece in pieces:
        chunk = {"choices": [{"delta": {"content": piece}, "finish_reason": None}]}
        lines += [f"data: {json.dumps(chunk)}", ""]
    final = {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": used}
    lines += [f"data: {json.dumps(final)}", "", "data: [DONE]", ""]
    return httpx.Response(200, content="\n".join(lines).encode())


def embeddings_answer(vectors: list[list[float]], used: Json) -> httpx.Response:
    """An embeddings answer, its rows in reverse order to test the reordering by index."""
    data = [{"object": "embedding", "index": index, "embedding": vector}
            for index, vector in enumerate(vectors)]  # fmt: skip
    return httpx.Response(200, json={"object": "list", "data": data[::-1], "usage": used})


def rerank_answer(
    scores: list[tuple[int, float]], search_units: int, cost: float | None
) -> httpx.Response:
    """A rerank answer; `cost` None leaves it out, as some rerank providers do."""
    used: Json = {"search_units": search_units}
    if cost is not None:
        used["cost"] = cost
    results = [{"index": index, "relevance_score": score, "document": {"text": ""}}
               for index, score in scores]  # fmt: skip
    return httpx.Response(200, json={"model": "probe/rerank", "results": results, "usage": used})


def image_answer(data: bytes, media_type: str, used: Json) -> httpx.Response:
    """An image answer: the picture as a data URL in `message.images`."""
    url = f"data:{media_type};base64,{base64.b64encode(data).decode()}"
    message = {"role": "assistant", "content": None, "images": [{"image_url": {"url": url}}]}
    return httpx.Response(200, json={"choices": [{"message": message}], "usage": used})
