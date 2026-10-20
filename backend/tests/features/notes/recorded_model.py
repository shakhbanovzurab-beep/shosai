"""OpenRouter for the notes' tests: an answer per question, every request kept.

`RecordedModel` tells each question by its content — a window of the findings by its
part's header, the merge, the summary — and serves the answers queued for it in order,
the last one again once the queue is down to it. A queued status fails the request.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.features.notes.infrastructure.prompts import ASK_AGAIN
from tests.doubles.openrouter import chat_answer, usage

type Json = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Asked:
    """One request the model received: which question, its part, whether asked again."""

    call: str
    part: int | None
    again: bool
    messages: list[tuple[str, str]]

    @property
    def data(self) -> str:
        """The text of the question's data, its first user message."""
        return next(text for role, text in self.messages if role == "user")


def _texts(body: Json) -> list[tuple[str, str]]:
    return [(m["role"], "".join(p.get("text", "") for p in m["content"])) for m in body["messages"]]


def _question(messages: list[tuple[str, str]]) -> tuple[str, int | None]:
    system, data = messages[0][1], messages[1][1]
    if system.startswith("You extract"):
        header = data.split("\n", 1)[0]
        return "window", int(header.removeprefix("Transcript, part ").split(" of ")[0])
    return ("merge" if system.startswith("You merge") else "summary"), None


@dataclass
class RecordedModel:
    """Answers per question, served in order; every request it received."""

    answers: dict[tuple[str, int | None], list[str | int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    asked: list[Asked] = field(default_factory=list)

    def answer(self, call: str, *answers: str | int, part: int | None = None) -> None:
        """Queue answers — a text, or an HTTP status to fail with — for a question."""
        self.answers[call, part].extend(answers)

    def of(self, call: str) -> list[Asked]:
        """The requests of one kind of question, in order."""
        return [asked for asked in self.asked if asked.call == call]

    def client(self) -> httpx.AsyncClient:
        """An HTTPX client whose transport is this model."""
        return httpx.AsyncClient(
            base_url=OPENROUTER_API + "/", transport=httpx.MockTransport(self._handle)
        )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        messages = _texts(json.loads(request.content))
        call, part = _question(messages)
        self.asked.append(Asked(call, part, messages[-1][1] == ASK_AGAIN, messages))
        queue = self.answers.get((call, part)) or self.answers.get((call, None))
        if not queue:
            return httpx.Response(500, json={"error": {"message": f"no answer for {call}"}})
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, int):
            return httpx.Response(answer, json={"error": {"message": "scripted failure"}})
        return chat_answer(answer, usage(len(json.dumps(messages)) // 4, 50, cost=0.0012))
