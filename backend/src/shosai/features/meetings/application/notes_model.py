"""Asking the notes' model and reading its answer (plan §3.4 flow 6; resilience-failure).

Every call goes through the AI port under the run's effect key: part `n` of a stage is
asked under `2n` and asked again under `2n + 1`, two calls and two cost rows (inv-9); a
redelivered stage repeats both keys and writes no cost row twice. The answer is one JSON
object in the text, of a Pydantic shape; a code fence around it is tolerated. An answer
that is empty, cut short or not that object is asked again once, with the bad text and a
request for the object alone; a second miss is counted and logged, and the caller goes on
without it. A provider's failure (`AiCallError`) is not an answer: it reaches the engine,
which retries the stage.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import structlog
from pydantic import BaseModel, ValidationError

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.port import AiProviders
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.features.meetings.application.pipeline import StageWork
from shosai.features.meetings.domain.runs import effect_key
from shosai.features.meetings.infrastructure.notes_metrics import (
    AnswerOutcome,
    NotesCall,
    NotesMetrics,
)
from shosai.features.meetings.infrastructure.prompts import ASK_AGAIN

# Один вызов укладывается в срок стадии (15 минут) вместе с окнами и повтором.
CALL_DEADLINE: Final = timedelta(minutes=3)
TEMPERATURE: Final = 0.2
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Question:
    """One call: which, its part of the stage, its instructions, its data and its bound."""

    call: NotesCall
    part: int
    instructions: str
    data: str
    max_output_tokens: int


def _message(role: Role, text: str) -> ChatMessage:
    return ChatMessage(role, (TextPart(text),))


def json_object_of[A: BaseModel](text: str, shape: type[A]) -> A | None:
    """The answer's JSON object in the shape, or None when the text holds none."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return shape.model_validate_json(text[start : end + 1])
    except ValidationError:
        return None


class NotesModel:
    """The notes' model behind the AI port, asked under a run's effect keys."""

    def __init__(self, ai: AiProviders, route: ModelRoute, metrics: NotesMetrics) -> None:
        self._ai = ai
        self._route = route
        self._metrics = metrics

    async def ask[A: BaseModel](
        self, work: StageWork, question: Question, shape: type[A], *, consent: bool
    ) -> A | None:
        """The answer in its shape, asking once more when the first is unreadable."""
        messages = (
            _message(Role.SYSTEM, question.instructions),
            _message(Role.USER, question.data),
        )
        first = await self._chat(work, (question, 2 * question.part), messages, consent=consent)
        answer = json_object_of(first, shape)
        if answer is not None:
            self._metrics.answered(question.call, AnswerOutcome.READ)
            return answer
        retold = (_message(Role.ASSISTANT, first),) if first.strip() else ()
        again = (*messages, *retold, _message(Role.USER, ASK_AGAIN))
        second = await self._chat(work, (question, 2 * question.part + 1), again, consent=consent)
        answer = json_object_of(second, shape)
        if answer is not None:
            self._metrics.answered(question.call, AnswerOutcome.READ_AGAIN)
            return answer
        self._metrics.answered(question.call, AnswerOutcome.LOST)
        log.warning(
            "Ответ модели заметок не прочитан и после повтора",
            run_id=str(work.run_id),
            call=question.call.value,
            part=question.part,
        )
        return None

    async def _chat(
        self,
        work: StageWork,
        keyed: tuple[Question, int],
        messages: tuple[ChatMessage, ...],
        *,
        consent: bool,
    ) -> str:
        question, part = keyed
        context = CallContext(
            effect_key=effect_key(work.run_id, work.stage, part),
            feature=f"meetings.{work.stage.value}",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.BACKGROUND,
            scope=work.scope,
            cross_border_consent=consent,
            deadline=CALL_DEADLINE,
        )
        request = ChatRequest(
            messages=messages,
            max_output_tokens=question.max_output_tokens,
            temperature=TEMPERATURE,
        )
        result = await self._ai.chat(context, self._route, request)
        return result.text
