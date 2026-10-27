"""Asking the extraction model for a turn's statements (memory step 5, Leo §7.2 "Extract").

The model reads the person's latest message, and the two exchanges before it for references
only, and answers one JSON object of the shape in `extraction_prompts`. An unreadable answer
is asked again once with a request for the object alone; a second miss gives no statements,
counted. The call is the person's background work under their consent, outside their Leo
tokens, keyed by the run: a redelivered admission pays once.
"""

from collections.abc import Sequence
from datetime import timedelta
from typing import Final, Protocol

from pydantic import BaseModel, ValidationError

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ai.results import ChatResult
from shosai.features.agent.contracts.memory import TurnWords
from shosai.features.memory.domain.admission import STATEMENTS_PER_TURN, Statement
from shosai.features.memory.domain.facts import (
    EXTRACTED_MAX,
    FactKind,
    MemoryRuleError,
    clean_statement,
)
from shosai.features.memory.infrastructure.embeddings import Payer
from shosai.features.memory.infrastructure.extraction_prompts import (
    ASK_AGAIN,
    EARLIER,
    LATEST,
    LEO_SAID,
    PERSON_SAID,
    TURN_INSTRUCTIONS,
    TurnAnswer,
)

DEADLINE: Final = timedelta(seconds=60)
MAX_OUTPUT_TOKENS: Final = 600
TEMPERATURE: Final = 0.1


def json_object_of[A: BaseModel](text: str, shape: type[A]) -> A | None:
    """The answer's JSON object in the shape, or None when the text holds none."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return shape.model_validate_json(text[start : end + 1])
    except ValidationError:
        return None


def turn_data(words: TurnWords) -> str:
    """What the model reads of a turn: the earlier exchanges, then the latest message."""
    parts: list[str] = []
    if words.before:
        parts.append(EARLIER)
        for exchange in words.before:
            parts += [PERSON_SAID.format(text=exchange.question)]
            if exchange.answer_head:
                parts += [LEO_SAID.format(text=exchange.answer_head)]
    parts += [LATEST, words.text]
    return "\n".join(parts)


def statements_of(answer: TurnAnswer) -> list[Statement]:
    """The answer's statements that keep the rules, at most three."""
    found: list[Statement] = []
    for item in answer.statements[:STATEMENTS_PER_TURN]:
        try:
            text = clean_statement(item.statement, EXTRACTED_MAX)
        except MemoryRuleError:
            continue
        found.append(
            Statement(text, FactKind(item.kind), item.explicit, item.sensitive, item.about_person)
        )
    return found


class ChatPort(Protocol):
    """The provider port's chat call."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer to a conversation."""
        ...


class Extractor:
    """The extraction model behind the AI port."""

    def __init__(self, ai: ChatPort, route: ModelRoute) -> None:
        self._ai = ai
        self._route = route

    async def turn(self, payer: Payer, words: TurnWords, key: str) -> list[Statement]:
        """The turn's statements; none when the model answers nothing readable twice."""
        messages: Sequence[ChatMessage] = (
            ChatMessage(Role.SYSTEM, (TextPart(TURN_INSTRUCTIONS),)),
            ChatMessage(Role.USER, (TextPart(turn_data(words)),)),
        )
        for attempt in range(2):
            text = await self._ask(payer, messages, f"memory.extract:{key}:{attempt}")
            answer = json_object_of(text, TurnAnswer)
            if answer is not None:
                return statements_of(answer)
            messages = (
                *messages,
                ChatMessage(Role.ASSISTANT, (TextPart(text),)),
                ChatMessage(Role.USER, (TextPart(ASK_AGAIN),)),
            )
        return []

    async def _ask(self, payer: Payer, messages: Sequence[ChatMessage], key: str) -> str:
        context = CallContext(
            effect_key=key,
            feature="memory.extract",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.BACKGROUND,
            scope=payer.scope,
            cross_border_consent=payer.consent,
            deadline=DEADLINE,
        )
        request = ChatRequest(
            messages=tuple(messages), max_output_tokens=MAX_OUTPUT_TOKENS, temperature=TEMPERATURE
        )
        answer = await self._ai.chat(context, self._route, request)
        return answer.text
