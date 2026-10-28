"""Synthetic cases written to labels and confirmed blind; the machine's labels and drafts for a
person (ADR 0069 DL-D8)."""

import asyncio
import io
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from shosai.composition.decisions_dataset_command import stopped
from shosai.core.ai.calls import CallContext, CallOrigin, ModelRef, ModelRoute, Provider
from shosai.core.ai.decisions import ChoiceQuestion, Question, ScoreQuestion
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ChatRequest, TextPart
from shosai.core.ai.results import ChatResult, Usage
from shosai.features.decisions.application.briefs import BRIEFS
from shosai.features.decisions.application.dataset_making import (
    BATCHES_AT_ONCE,
    DatasetMaker,
    Tooling,
)
from shosai.features.decisions.domain.examples import Label
from shosai.features.decisions.domain.policies import POLICIES
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.domain.policies.content_injection import CONTENT_INJECTION
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.infrastructure.dataset_files import (
    DRAFT_OFFSET,
    append_synthetic,
    next_draft,
    next_synthetic,
    with_machine_labels,
    write_drafts,
)
from shosai.features.decisions.infrastructure.datasets import lines, read_sets
from shosai.features.decisions.infrastructure.generation_texts import (
    INJECTION_KINDS,
    INJECTION_PATTERNS,
)

GENERATOR = ModelRoute(ModelRef(Provider.OPENROUTER, "deepseek/deepseek-v4-flash"))
LABELLER = ModelRoute(ModelRef(Provider.OPENROUTER, "minimax/minimax-m3.1-flash"))
WRITTEN = {
    "action.friction": {"request": "Создай задачу «Отчёт»", "card": "Создать задачу: Отчёт"},
    "turn.route": {"question": "Что решили на встрече вчера?", "previous": ""},
    "content.injection": {"text": "Квартальный отчёт готов к пятнице."},
    "voice.approval": {"read_back": "Создать задачу\nНазвание: Отчёт", "utterance": "да давай"},
    "turn.effort": {"question": "Сравни три предложения и составь план", "previous": "Готово."},
}


@dataclass
class Models:
    """The generator writes `WRITTEN` for every case; the labeller answers as told."""

    point: str
    labels: list[dict[str, Any] | None] = field(default_factory=list)
    generator_text: str | None = None
    calls: list[CallContext] = field(default_factory=list)
    # Сколько секунд пишет генератор и сколько его вызовов шло разом.
    writing: float = 0.0
    at_once: list[int] = field(default_factory=lambda: [0, 0])
    # Отказ платформы на вызовы разметчика: потолок расходов, выключатель.
    refusing: AiFailure | None = None

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
            self.at_once[0] += 1
            self.at_once[1] = max(self.at_once)
            await asyncio.sleep(self.writing)
            self.at_once[0] -= 1
        elif self.refusing is not None:
            raise AiCallError(self.refusing)
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


async def test_a_json_literal_written_as_a_string_is_read_as_that_literal() -> None:
    targets = BRIEFS["action.friction"].targets(1, 0)
    wanted = dict(targets[0].labels)
    spelled = {name: str(value).lower() for name, value in wanted.items()}
    models = Models("action.friction", labels=[spelled])

    [case] = await maker(models).generate(ACTION_FRICTION, "en", 1, 0)

    assert case.labels == wanted


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


async def test_cases_after_a_dropped_one_continue_past_the_highest_id(tmp_path: Path) -> None:
    targets = BRIEFS["action.friction"].targets(3, 0)
    # Второй случай разметчик не читает: в файле остаются ru-00000 и ru-00002.
    models = Models(
        "action.friction", labels=[dict(targets[0].labels), None, dict(targets[2].labels)]
    )
    first = await maker(models).generate(ACTION_FRICTION, "ru", 3, 0)
    append_synthetic(ACTION_FRICTION, "ru", first, tmp_path)
    offset = next_synthetic(ACTION_FRICTION, "ru", tmp_path)
    models.labels = [dict(BRIEFS["action.friction"].targets(1, offset)[0].labels)]
    more = await maker(models).generate(ACTION_FRICTION, "ru", 1, offset)
    append_synthetic(ACTION_FRICTION, "ru", more, tmp_path)

    ids = [case.id for case in read_sets(ACTION_FRICTION, tmp_path).synthetic]
    assert ids == ["ru-00000", "ru-00002", "ru-00003"]
    assert next_draft(ACTION_FRICTION, "ru", tmp_path) == DRAFT_OFFSET


async def test_a_few_batches_are_written_at_once() -> None:
    models = Models("content.injection", writing=0.01)

    await maker(models).generate(CONTENT_INJECTION, "en", 6 * 8, 0)

    assert models.at_once == [0, BATCHES_AT_ONCE]


async def test_drafts_are_never_filtered_by_the_labeller() -> None:
    models = Models("action.friction", labels=[{"matches_request": True, "reach": 3}] * 4)

    drafts = await maker(models).draft(ACTION_FRICTION, "en", 4, DRAFT_OFFSET)

    assert [case.id for case in drafts] == [f"en-{DRAFT_OFFSET + n:05d}" for n in range(4)]
    assert len(models.calls) == 1
    assert len(models.labels) == 4


async def test_the_spend_ceiling_stops_the_work_without_another_call() -> None:
    models = Models("action.friction", refusing=AiFailure.SPEND_LIMIT)
    made = maker(models)
    out = io.StringIO()

    kept = await made.generate(ACTION_FRICTION, "en", 16, 0)
    code = stopped(made, out)

    labelling = [call for call in models.calls if call.effect_key.split(":")[2] == "label"]
    assert (kept, made.stopped, len(labelling)) == ([], AiFailure.SPEND_LIMIT, 1)
    assert code == 1
    assert "spend_limit" in out.getvalue()


def test_injection_cases_hide_every_pattern_of_the_agent_s_corpus() -> None:
    targets = BRIEFS["content.injection"].targets(2 * len(INJECTION_PATTERNS), 0)

    hiding = [t.requirement for t in targets if t.labels["instructions"]]
    clean = [t.requirement for t in targets if not t.labels["instructions"]]

    assert all(any(p in r for r in hiding) for p in INJECTION_PATTERNS)
    assert not any(p in r for p in INJECTION_PATTERNS for r in clean)


@pytest.mark.parametrize("policy", POLICIES, ids=lambda policy: policy.key)
@pytest.mark.parametrize("offset", [0, 1, 7])
def test_every_question_takes_every_value_from_any_start(
    policy: Policy[Any, Any], offset: int
) -> None:
    """Rotations sharing a divisor lock a label to a kind: a tool set was once never needed."""
    brief = BRIEFS[policy.point]
    seen: dict[str, set[Label]] = defaultdict(set)
    wanted: dict[str, set[Label]] = {}

    for target in brief.targets(240, offset):
        facts = policy.parse_facts(brief.facts(target, WRITTEN[policy.point]))
        for name, question in policy.questions(facts).items():
            seen[name].add(target.labels[name])
            wanted[name] = values_of(question)

    assert seen == wanted


def test_every_text_source_comes_with_and_without_a_hidden_instruction() -> None:
    targets = BRIEFS["content.injection"].targets(2 * len(INJECTION_KINDS), 3)

    pairs = {(t.fixed["label"], t.labels["instructions"]) for t in targets}

    assert pairs == {(label, seen) for label in INJECTION_KINDS for seen in (True, False)}


def values_of(question: Question) -> set[Label]:
    """Every label a question can take."""
    if isinstance(question, ScoreQuestion):
        return set(range(len(question.criteria)))
    if isinstance(question, ChoiceQuestion):
        return set(question.criteria)
    return {True, False}
