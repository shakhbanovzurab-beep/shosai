"""A donated evaluation case replayed against today's model and policy (ADR 0068 AG-D13, AG-D8;
agent step 11c).

A case is the turn as the model read it. The replay asks the standard model the same message
with the tool results the case kept, under today's policy and in the case's language, with no
tool to call — the data is what the person's tools returned then — and a judge compares the new
answer with the one the person rated. A "Not useful" case passes when the new answer is better,
a "Useful" one when it is not worse; a judge that fails or answers outside its format leaves the
case ungraded. Both calls are the platform's own; only the verdict leaves the replay.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Literal
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute, PlatformAccount
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatRequest, Role
from shosai.core.i18n.locales import LOCALE_BY_CODE
from shosai.core.kernel.ids import new_id
from shosai.features.agent.application.eval_judge import (
    JUDGE_OUTPUT_TOKENS,
    RESULTS_CHARS,
    ModelChats,
)
from shosai.features.agent.application.run_context import text_message
from shosai.features.agent.domain.feedback import Rating
from shosai.features.agent.infrastructure.eval_prompts import (
    COMPARE,
    COMPARE_CASE,
    NO_RESULTS,
    RATED,
    REPLAY_RESULTS,
)
from shosai.features.agent.infrastructure.prompts import LANGUAGE, POLICY

REPLAY_FEATURE: Final = "agent.eval_replay"
# Ответ повтора — как обычный ответ Leo: короткий запас сверх длинного ответа.
ANSWER_TOKENS: Final = 2_000
log = structlog.stdlib.get_logger(__name__)


class Verdict(StrEnum):
    """How the new answer compares with the one the person rated."""

    BETTER = "better"
    SAME = "same"
    WORSE = "worse"


@dataclass(frozen=True, slots=True)
class StoredCase:
    """A case as its home keeps it."""

    id: UUID
    rating: Rating
    language: str
    case: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CaseScore:
    """What a replay keeps: the case by id, its rating and language, and the verdict."""

    case_id: UUID
    rating: Rating
    language: str
    verdict: Verdict | None

    @property
    def passed(self) -> bool | None:
        """A "Not useful" case must get better, a "Useful" one must not get worse."""
        if self.verdict is None:
            return None
        if self.rating is Rating.NOT_USEFUL:
            return self.verdict is Verdict.BETTER
        return self.verdict is not Verdict.WORSE


class CompareAnswer(BaseModel):
    """The judge's verdict as it must be written: JSON types exactly, no coercion."""

    model_config = ConfigDict(strict=True)

    verdict: Literal["better", "same", "worse"]
    reason: str = Field(max_length=500)


def verdict_of(text: str) -> Verdict | None:
    """The verdict in the judge's answer — its one JSON object — or None when there is none."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        answer = CompareAnswer.model_validate(json.loads(text[start : end + 1]))
    except ValueError, ValidationError:
        return None
    return Verdict(answer.verdict)


def results_of(case: dict[str, Any]) -> str:
    """The digests the model read in the case's rounds, by tool."""
    parts = [
        f"{result.get('tool', '')}: {result.get('digest', '')}"
        for round_ in case.get("rounds", [])
        for result in round_.get("results", [])
    ]
    return "\n".join(parts)[:RESULTS_CHARS]


def platform_call(feature: str) -> CallContext:
    """A call of the platform's own, under a key of its own."""
    return CallContext(
        effect_key=f"{feature}:{new_id()}",
        feature=feature,
        call_class=CallClass.STANDARD,
        origin=CallOrigin.SYSTEM,
        platform_account=PlatformAccount.SYSTEM,
    )


class CaseReplay:
    """Replays cases and has their answers compared."""

    def __init__(self, ai: ModelChats, routes: tuple[ModelRoute, ModelRoute]) -> None:
        self._ai = ai
        self._answering, self._judging = routes

    async def score(self, stored: StoredCase) -> CaseScore:
        """The case's verdict; an answer or a judge that failed leaves it ungraded."""
        locale = LOCALE_BY_CODE.get(stored.language) or LOCALE_BY_CODE["en"]
        results = results_of(stored.case)
        head = f"{POLICY}\n\n{LANGUAGE.format(code=locale.code, name=locale.endonym)}"
        if results:
            head += "\n\n" + REPLAY_RESULTS.format(results=results)
        question = str(stored.case.get("question", ""))
        answer = await self._ask(
            ChatRequest(
                messages=(text_message(Role.SYSTEM, head), text_message(Role.USER, question)),
                max_output_tokens=ANSWER_TOKENS,
            ),
            self._answering,
        )
        verdict = None
        if answer is not None:
            case = COMPARE_CASE.format(
                code=locale.code, name=locale.endonym, question=question,
                results=results or NO_RESULTS, rating=RATED[stored.rating.value],
                earlier=str(stored.case.get("answer", "")), answer=answer,
            )  # fmt: skip
            judged = await self._ask(
                ChatRequest(
                    messages=(text_message(Role.SYSTEM, COMPARE), text_message(Role.USER, case)),
                    max_output_tokens=JUDGE_OUTPUT_TOKENS,
                    temperature=0.0,
                ),
                self._judging,
            )
            verdict = verdict_of(judged) if judged is not None else None
        return CaseScore(stored.id, stored.rating, stored.language, verdict)

    async def _ask(self, request: ChatRequest, route: ModelRoute) -> str | None:
        try:
            result = await self._ai.chat(platform_call(REPLAY_FEATURE), route, request)
        except AiCallError as error:
            log.warning("Модель не ответила при повторе оценочного случая", code=error.code)
            return None
        return result.text
