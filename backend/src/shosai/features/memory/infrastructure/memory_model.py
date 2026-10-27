"""Memory's calls of its model: one JSON object, asked once more when unreadable (steps 5, 7).

The extraction, the summary's writer and the "Ask or update" box each send their registered
instructions and the person's data, and read one JSON object of their shape. An unreadable
answer is asked again once with a request for the object alone; a second miss gives nothing.
Every call is the person's, under their consent and outside their Leo tokens, keyed so a
repeated task or request pays once per attempt.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, Protocol

from pydantic import BaseModel, ValidationError

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ai.results import ChatResult
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.extraction_prompts import ASK_AGAIN

DEADLINE: Final = timedelta(seconds=60)
TEMPERATURE: Final = 0.1
ATTEMPTS: Final = 2


def json_object_of[A: BaseModel](text: str, shape: type[A]) -> A | None:
    """The answer's JSON object in the shape, or None when the text holds none."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return shape.model_validate_json(text[start : end + 1])
    except ValidationError:
        return None


class ChatPort(Protocol):
    """The provider port's chat call."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer to a conversation."""
        ...


@dataclass(frozen=True, slots=True)
class ModelCall:
    """What a call is for, its key, who started it and how long its answer may be."""

    feature: str
    key: str
    origin: CallOrigin
    max_output_tokens: int


class MemoryModel:
    """Memory's model behind the AI port."""

    def __init__(self, ai: ChatPort, route: ModelRoute) -> None:
        self._ai = ai
        self._route = route

    async def answer[A: BaseModel](
        self, payer: Payer, call: ModelCall, data: tuple[str, str], shape: type[A]
    ) -> A | None:
        """The object of the shape for the instructions and the data; None after two misses."""
        instructions, text = data
        messages: Sequence[ChatMessage] = (
            ChatMessage(Role.SYSTEM, (TextPart(instructions),)),
            ChatMessage(Role.USER, (TextPart(text),)),
        )
        for attempt in range(ATTEMPTS):
            said = await self._ask(payer, call, messages, attempt)
            found = json_object_of(said, shape)
            if found is not None:
                return found
            messages = (
                *messages,
                ChatMessage(Role.ASSISTANT, (TextPart(said),)),
                ChatMessage(Role.USER, (TextPart(ASK_AGAIN),)),
            )
        return None

    async def _ask(
        self, payer: Payer, call: ModelCall, messages: Sequence[ChatMessage], attempt: int
    ) -> str:
        context = CallContext(
            effect_key=f"{call.key}:{attempt}",
            feature=call.feature,
            call_class=CallClass.STANDARD,
            origin=call.origin,
            scope=payer.scope,
            cross_border_consent=payer.consent,
            deadline=DEADLINE,
        )
        request = ChatRequest(
            messages=tuple(messages),
            max_output_tokens=call.max_output_tokens,
            temperature=TEMPERATURE,
        )
        answer = await self._ai.chat(context, self._route, request)
        return answer.text
