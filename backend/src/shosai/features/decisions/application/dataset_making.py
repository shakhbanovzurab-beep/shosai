"""Writing synthetic cases and labelling cases blind (ADR 0069 DL-D8).

The generator writes, in one call per batch, the text of cases whose labels the code chose;
each written case is then labelled blind by a model of another provider through the policy's
own questions, and kept only when the two agree. The same labeller fills the machine's labels
of a person's reference cases. Every call is the platform's own, keyed by the run and the
case, and answers JSON; an answer that is not is a case lost, logged, never a guess.
"""

import asyncio
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute, PlatformAccount
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ai.results import ChatResult
from shosai.features.decisions.application.briefs import BRIEFS, Target
from shosai.features.decisions.domain.examples import Case, Label, check_labels
from shosai.features.decisions.domain.policy import Policy, question_text
from shosai.features.decisions.infrastructure.generation_texts import (
    BRIEF_TEXTS,
    GENERATOR_REQUEST,
    GENERATOR_SYSTEM,
    LABELLER_REQUEST,
    LABELLER_SYSTEM,
    LANGUAGE_NAMES,
    SHAPES,
)

BATCH: Final = 8
# Пакетов в работе разом: до 32 вызовов разметчика, а не три часа подряд на 2 400 случаев.
BATCHES_AT_ONCE: Final = 4
GENERATION_TOKENS: Final = 8_000
LABEL_TOKENS: Final = 400
log = structlog.stdlib.get_logger(__name__)


class ChatPort(Protocol):
    """The provider port's chat."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A model's answer."""
        ...


def json_object(text: str) -> dict[str, Any] | None:
    """The answer's JSON object, or None when it holds none."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


@dataclass(frozen=True, slots=True)
class Tooling:
    """The chat port and the two models: the generator's and the labeller's."""

    chat: ChatPort
    generator: ModelRoute
    labeller: ModelRoute


class DatasetMaker:
    """Writes synthetic cases for a point and labels cases blind."""

    def __init__(self, tooling: Tooling) -> None:
        self._tooling = tooling
        self._run = uuid.uuid4().hex[:12]

    async def label(self, policy: Policy[Any, Any], case: Case) -> Mapping[str, Label] | None:
        """The labeller's labels of a case, or None when it gave none of the right kinds."""
        questions = policy.questions(case.facts)
        listing = json.dumps({name: question_text(q) for name, q in questions.items()}, indent=1)
        state = json.dumps(policy.state(case.facts), ensure_ascii=False, indent=1)
        prompt = LABELLER_REQUEST.format(case=state, questions=listing)
        answer = await self._ask(
            self._tooling.labeller, (LABELLER_SYSTEM, prompt), f"label:{case.id}", LABEL_TOKENS
        )
        if answer is None:
            return None
        try:
            check_labels(case.id, questions, answer, partial=False)
        except ValueError:
            return None
        return answer

    async def generate(
        self, policy: Policy[Any, Any], language: str, count: int, offset: int
    ) -> list[Case]:
        """Cases written to the code's labels and confirmed by the labeller, in their order;
        a few batches at a time, each batch's cases labelled together."""
        return await self._made(policy, language, (count, offset), confirm=True)

    async def draft(
        self, policy: Policy[Any, Any], language: str, count: int, offset: int
    ) -> list[Case]:
        """Cases for a person to label blind: never filtered by the labeller, since its
        agreement with the person is what the reference measures."""
        return await self._made(policy, language, (count, offset), confirm=False)

    async def _made(
        self, policy: Policy[Any, Any], language: str, sizing: tuple[int, int], *, confirm: bool
    ) -> list[Case]:
        count, offset = sizing
        targets = BRIEFS[policy.point].targets(count, offset)
        gate = asyncio.Semaphore(BATCHES_AT_ONCE)

        async def batch_of(start: int) -> list[Case | None]:
            async with gate:
                batch = targets[start : start + BATCH]
                written = await self._written(policy.point, language, batch, offset + start)
                cases = [
                    self._parsed(policy, language, target, (text, offset + start + number))
                    for number, (target, text) in enumerate(zip(batch, written, strict=False))
                ]
                if not confirm:
                    return cases
                return await asyncio.gather(*(self._confirmed(policy, case) for case in cases))

        batches = await asyncio.gather(*(batch_of(at) for at in range(0, len(targets), BATCH)))
        return [case for batch in batches for case in batch if case is not None]

    async def _written(
        self, point: str, language: str, batch: Sequence[Target], first: int
    ) -> list[Mapping[str, object]]:
        """The generator's cases of a batch; fewer, or none, when its answer falls short."""
        requirements = "\n".join(f"{n}. {t.requirement}" for n, t in enumerate(batch, start=1))
        prompt = GENERATOR_REQUEST.format(
            language=LANGUAGE_NAMES[language], brief=BRIEF_TEXTS[point],
            count=len(batch), requirements=requirements, shape=SHAPES[point],
        )  # fmt: skip
        key = f"generate:{point}:{language}:{first}"
        answer = await self._ask(
            self._tooling.generator, (GENERATOR_SYSTEM, prompt), key, GENERATION_TOKENS
        )
        cases = (answer or {}).get("cases")
        return [case for case in cases if isinstance(case, dict)] if isinstance(cases, list) else []

    def _parsed(
        self,
        policy: Policy[Any, Any],
        language: str,
        target: Target,
        written: tuple[Mapping[str, object], int],
    ) -> Case | None:
        """The case when its facts are in shape."""
        text, number = written
        try:
            facts = policy.parse_facts(BRIEFS[policy.point].facts(target, text))
        except ValueError:
            return None
        return Case(f"{language}-{number:05d}", language, facts, dict(target.labels))

    async def _confirmed(self, policy: Policy[Any, Any], case: Case | None) -> Case | None:
        """The case when the labeller agrees with its labels."""
        if case is None:
            return None
        labels = await self.label(policy, case)
        if labels != case.labels:
            log.info("Случай отброшен: разметчик не согласен", point=policy.point, case=case.id)
            return None
        return case

    async def _ask(
        self, route: ModelRoute, prompt: tuple[str, str], key: str, tokens: int
    ) -> dict[str, Any] | None:
        """A model's JSON answer as the platform's own call; None when there is none."""
        system, user = prompt
        request = ChatRequest(
            messages=(
                ChatMessage(Role.SYSTEM, (TextPart(system),)),
                ChatMessage(Role.USER, (TextPart(user),)),
            ),
            max_output_tokens=tokens,
        )
        context = CallContext(
            effect_key=f"dataset:{self._run}:{key}"[:200], feature="decisions.dataset",
            call_class=CallClass.STANDARD, origin=CallOrigin.SYSTEM,
            platform_account=PlatformAccount.SYSTEM,
        )  # fmt: skip
        try:
            result = await self._tooling.chat.chat(context, route, request)
        except AiCallError as error:
            log.warning("Модель набора не ответила", key=key, failure=error.failure.value)
            return None
        return json_object(result.text)
