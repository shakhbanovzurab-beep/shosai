"""Synthetic cases written to labels and confirmed blind; the machine's labels and drafts for a
person (ADR 0069 DL-D8)."""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from shosai.core.ai.calls import CallContext, CallOrigin, ModelRef, ModelRoute, Provider
from shosai.core.ai.requests import ChatRequest, TextPart
from shosai.core.ai.results import ChatResult, Usage
from shosai.features.decisions.application.briefs import BRIEFS
from shosai.features.decisions.application.dataset_making import DatasetMaker, Tooling
from shosai.features.decisions.domain.policies import POLICIES
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.domain.policies.content_injection import CONTENT_INJECTION
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.infrastructure.dataset_files import (
    append_synthetic,
    with_machine_labels,
    write_drafts,
)
from shosai.features.decisions.infrastructure.datasets import lines, read_sets

GENERATOR = ModelRoute(ModelRef(Provider.OPENROUTER, "anthropic/claude-sonnet-5.5"))
LABELLER = ModelRoute(ModelRef(Provider.OPENROUTER, "openai/gpt-5.6-terra"))
WRITTEN = {
    "action.friction": {"request": "Создай задачу «Отчёт»", "card": "Создать задачу: Отчёт"},
    "turn.route": {"question": "Что решили на встрече вчера?", "previous": ""},
    "content.injection": {"text": "Квартальный отчёт готов к пятнице."},
}


@dataclass
class Models:
    """The generator writes `WRITTEN` for every case; the labeller answers as told."""

    point: str
    labels: list[dict[str, Any] | None] = field(default_factory=list)
    generator_text: str | None = None
    calls: list[CallContext] = field(default_factory=list)

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """A JSON answer by the model asked."""
        self.calls.append(context)
        if route == GENERATOR:
            prompt = request.messages[-1].parts[0]
            assert isinstance(prompt, TextPart)
            count = int(prompt.text.split("Write exactly ")[1].split(" ")[0])
            text = self.generator_text or json.dumps({"cases": [WRITTEN[self.point]] * count})
        else:
            answer = self.labels.pop(0) if self.labels else None
            text = json.dumps(answer) if answer is not None else "no idea"
        return ChatResult(text, (), "stop", route.primary, Usage(input_tokens=10))


def maker(models: Models) -> DatasetMaker:
    """The maker over the doubles."""
    return DatasetMaker(Tooling(models, GENERATOR, LABELLER))


@pytest.mark.parametrize("policy", POLICIES, ids=lambda policy: policy.key)
def test_every_label_value_is_planned_evenly_and_every_case_parses(
    policy: Policy[Any, Any],
) -> None:
    brief = BRIEFS[policy.point]
    targets = brief.targets(96, 0)

    values = Counter(value for t in targets for value in t.labels.values())
    for target in targets:
        facts = policy.parse_facts(brief.facts(target, WRITTEN[policy.point]))
        assert set(policy.questions(facts)) == set(target.labels)
    assert len(values) >= 2
    assert min(values.values()) >= 24


async def test_a_case_is_kept_only_when_the_labeller_agrees() -> None:
    targets = BRIEFS["action.friction"].targets(2, 0)
    models = Models(
        "action.friction", labels=[dict(targets[0].labels), {"matches_request": True, "reach": 3}]
    )

    cases = await maker(models).generate(ACTION_FRICTION, "ru", 2, 0)

    assert [case.id for case in cases] == ["ru-00000"]
    assert cases[0].labels == targets[0].labels
    assert all(call.origin is CallOrigin.SYSTEM for call in models.calls)
    assert len({call.effect_key for call in models.calls}) == len(models.calls)


async def test_an_unreadable_answer_loses_the_case_never_guesses() -> None:
    chatty = Models("content.injection", generator_text="Sure! Here are the cases.")
    # Разметчик отвечает не тем видом метки: случай тоже теряется.
    wrong_kind = Models("content.injection", labels=[{"instructions": "maybe"}])

    lost = await maker(chatty).generate(CONTENT_INJECTION, "en", 3, 0)
    kept = await maker(wrong_kind).generate(CONTENT_INJECTION, "en", 1, 0)

    assert (lost, kept) == ([], [])


async def test_generated_cases_append_drafts_hide_labels_machine_labels_sit_beside(
    tmp_path: Path,
) -> None:
    targets = BRIEFS["action.friction"].targets(4, 0)
    models = Models("action.friction", labels=[dict(t.labels) for t in targets])
    cases = await maker(models).generate(ACTION_FRICTION, "ru", 4, 0)

    append_synthetic(ACTION_FRICTION, "ru", cases, tmp_path)
    drafts = write_drafts(ACTION_FRICTION, "ru", cases[:2], tmp_path)
    reference = tmp_path / "action_friction" / "reference" / "ru.jsonl"
    person = [{**json.loads(line), "labels": {"matches_request": False, "reach": 1}}
              for line in drafts.read_text(encoding="utf-8").splitlines()]  # fmt: skip
    reference.write_text("".join(json.dumps(row) + "\n" for row in person), encoding="utf-8")
    machine = {row["id"]: {"matches_request": True, "reach": 1} for row in person}
    written = with_machine_labels(reference, machine)

    sets = read_sets(ACTION_FRICTION, tmp_path)
    assert len(sets.synthetic) == 4
    assert all(row["labels"] == {} and "questions" in row for row in lines(drafts))
    assert written == 2
    assert [case.labels["matches_request"] for case in sets.reference] == [False, False]
    assert [case.machine_labels["matches_request"] for case in sets.reference] == [True, True]
