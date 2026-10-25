"""The live suite's judge: a model grades each answer (Leo §11.4, AG-D8).

The judge reads the question, the language the answer was due in, what the tools that ran
returned, the cards the turn proposed with their values, and the answer, and grades the
language, the grounding and the help. Its call is the
platform's own, paid by the system account, under its own effect key. A judge that fails or
answers outside its format leaves the case ungraded, which the report counts apart — it never
passes or fails a case it did not grade.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final, Protocol
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute, PlatformAccount
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatRequest, Role
from shosai.core.ai.results import ChatResult
from shosai.core.i18n.locales import LOCALE_BY_CODE
from shosai.core.kernel.ids import new_id
from shosai.features.agent.application.eval_world import PERSON_NAME, TIME_ZONE
from shosai.features.agent.application.run_context import text_message
from shosai.features.agent.domain.eval_cases import EvalScenario
from shosai.features.agent.domain.eval_checks import Observed
from shosai.features.agent.domain.eval_report import JudgeGrade
from shosai.features.agent.infrastructure.eval_prompts import (
    CARD,
    JUDGE,
    JUDGE_CASE,
    KNOWN,
    KNOWN_PAGE,
    NO_CARDS,
    NO_RESULTS,
)

JUDGE_FEATURE: Final = "agent.eval_judge"
# Время хода для судьи — так же, как его видит Leo в контексте.
MOMENT: Final = "%A, %d %B %Y, %H:%M"
# Рассуждения модели входят в предел вывода: короткому JSON нужен запас.
JUDGE_OUTPUT_TOKENS: Final = 1_500
# Сколько текста результатов видит судья: ответы сценариев малы, предел — от случайного роста.
RESULTS_CHARS: Final = 8_000
log = structlog.stdlib.get_logger(__name__)


class ModelChats(Protocol):
    """The provider port's chat, as the judge uses it."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The model's whole answer."""
        ...


class JudgeAnswer(BaseModel):
    """The judge's grade as it must be written: JSON types exactly, no coercion."""

    model_config = ConfigDict(strict=True)

    language: bool
    grounded: bool
    helpful: int = Field(ge=1, le=5)
    reason: str = Field(max_length=500)


def grade_of(text: str) -> JudgeGrade | None:
    """The grade in the judge's answer — its one JSON object, even with words or a fence around
    it — or None when there is none."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        answer = JudgeAnswer.model_validate(json.loads(text[start : end + 1]))
    except ValueError, ValidationError:
        return None
    return JudgeGrade(answer.language, answer.grounded, answer.helpful, answer.reason)


def tool_results(scenario: EvalScenario, observed: Observed) -> str:
    """What the tools that ran returned, in the order they first ran."""
    ran = dict.fromkeys(run.tool for run in observed.runs)
    parts = [
        f"{tool}: {json.dumps(scenario.fixtures[tool].output, ensure_ascii=False)}"
        for tool in ran
        if tool in scenario.fixtures
    ]
    return "\n".join(parts)[:RESULTS_CHARS] or NO_RESULTS


def proposed_cards(observed: Observed) -> str:
    """The writes the turn proposed as cards, with the values the person would approve."""
    lines = [
        CARD.format(tool=run.tool, arguments=json.dumps(run.arguments, ensure_ascii=False))
        for run in observed.proposed
    ]
    return "\n".join(lines)[:RESULTS_CHARS] or NO_CARDS


def known_before(scenario: EvalScenario, now: datetime) -> str:
    """What Leo knew before any tool: the person's profile, the time and the page's subject."""
    moment = now.astimezone(ZoneInfo(TIME_ZONE)).strftime(MOMENT)
    known = KNOWN.format(person=PERSON_NAME, zone=TIME_ZONE, moment=moment)
    subject = scenario.subject
    if subject is not None:
        known += KNOWN_PAGE.format(kind=subject.kind, title=subject.title)
    return known


class Judge:
    """Grades answers with a model."""

    def __init__(
        self,
        ai: ModelChats,
        route: ModelRoute,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._ai = ai
        self._route = route
        self._clock = clock

    async def grade(
        self, scenario: EvalScenario, language: str, observed: Observed
    ) -> JudgeGrade | None:
        """The grade of one answer, or None when the judge did not give one."""
        locale = LOCALE_BY_CODE[language]
        case = JUDGE_CASE.format(
            code=locale.code,
            name=locale.endonym,
            known=known_before(scenario, self._clock()),
            question=scenario.question(language),
            results=tool_results(scenario, observed),
            cards=proposed_cards(observed),
            answer=observed.answer,
        )
        request = ChatRequest(
            messages=(text_message(Role.SYSTEM, JUDGE), text_message(Role.USER, case)),
            max_output_tokens=JUDGE_OUTPUT_TOKENS,
            temperature=0.0,
        )
        context = CallContext(
            effect_key=f"{JUDGE_FEATURE}:{new_id()}",
            feature=JUDGE_FEATURE,
            call_class=CallClass.STANDARD,
            origin=CallOrigin.SYSTEM,
            platform_account=PlatformAccount.SYSTEM,
        )
        try:
            result = await self._ai.chat(context, self._route, request)
        except AiCallError as error:
            log.warning("Судья оценки не ответил", code=error.code, scenario=scenario.id)
            return None
        grade = grade_of(result.text)
        if grade is None:
            log.warning(
                "Судья оценки ответил не по формату",
                scenario=scenario.id, finish=result.finish_reason, chars=len(result.text),
            )  # fmt: skip
        return grade
