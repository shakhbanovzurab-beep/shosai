"""Labelled cases and Jev's answers to them, as data (Leo §6.4, ADR 0069 DL-D8).

A case is a policy's facts with a label per question — `true`/`false` for a `noul`, a level
for a `score`, an option for a `choice` — in one language. A reference case also keeps the
labels the machine gave it, compared with the person's. From labels come the truth of each
signal and the outcome the case expects, so a fitted policy is judged on what it decides,
not only on its probabilities. Jev's answers are kept as plain data, so a recorded run is
re-read exactly in CI without a call.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from shosai.core.ai.decisions import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.domain.verdicts import Signal, Verdict

type Label = bool | int | str


@dataclass(frozen=True, slots=True)
class Case:
    """A labelled case of one policy in one language."""

    id: str
    language: str
    facts: Any
    labels: Mapping[str, Label]
    # Метки машины для эталонного случая: с ними сверяется разметка человека.
    machine_labels: Mapping[str, Label] = field(default_factory=dict)


def parsed_case(policy: Policy[Any, Any], raw: Mapping[str, object]) -> Case:
    """A case as a dataset line holds it; `ValueError` names what is off."""
    case_id, language = raw.get("id"), raw.get("language")
    facts, labels = raw.get("facts"), raw.get("labels")
    if not isinstance(case_id, str) or not isinstance(language, str):
        message = "у случая — строковые id и language"
        raise ValueError(message)
    if not isinstance(facts, dict) or not isinstance(labels, dict):
        message = f"случай {case_id}: facts и labels — объекты"
        raise ValueError(message)
    parsed = policy.parse_facts(facts)
    questions = policy.questions(parsed)
    machine = raw.get("machine_labels") or {}
    if not isinstance(machine, dict):
        message = f"случай {case_id}: machine_labels — объект"
        raise ValueError(message)
    for given in (labels, machine):
        check_labels(case_id, questions, given, partial=given is machine)
    return Case(case_id, language, parsed, dict(labels), dict(machine))


def check_labels(
    case_id: str, questions: Mapping[str, Question], labels: Mapping[str, object], *, partial: bool
) -> None:
    """Every question labelled in its own kind; machine labels may be absent until labelled."""
    if (set(labels) != set(questions)) and not (partial and not labels):
        message = f"случай {case_id}: метки не совпадают с вопросами политики"
        raise ValueError(message)
    for name, label in labels.items():
        if not fits(questions[name], label):
            message = f"случай {case_id}: метка {name} не того вида"
            raise ValueError(message)


def fits(question: Question, label: object) -> bool:
    """Whether a label is of its question's kind."""
    if isinstance(question, ScoreQuestion):
        top = len(question.criteria) - 1
        return isinstance(label, int) and not isinstance(label, bool) and 0 <= label <= top
    if isinstance(question, ChoiceQuestion):
        return isinstance(label, str) and label in question.criteria
    return isinstance(label, bool)


def truth(signal: Signal, label: Label) -> bool:
    """Whether a signal's proposition holds for a label."""
    if signal.at_least is not None:
        return isinstance(label, int) and label >= signal.at_least
    if signal.option is not None:
        return label == signal.option
    return label is True


def expected[F, V](policy: Policy[F, V], case: Case) -> V:
    """The outcome the case's labels call for."""
    signals = policy.signals(case.facts)
    truths = {name: truth(signal, case.labels[name]) for name, signal in signals.items()}
    verdicts = {name: Verdict.YES if held else Verdict.NO for name, held in truths.items()}
    chances = {name: 1.0 if held else 0.0 for name, held in truths.items()}
    return policy.outcome(case.facts, verdicts, chances)


def answer_json(answer: Answer) -> dict[str, object]:
    """An answer as plain data."""
    if isinstance(answer, NoulAnswer):
        return {"type": "noul", "probability": answer.probability}
    if isinstance(answer, ChoiceAnswer):
        return {
            "type": "choice",
            "choice": answer.choice,
            "probabilities": dict(answer.probabilities),
        }
    return {"type": "score", "score": answer.score, "probabilities": dict(answer.probabilities)}


def answer_of(raw: Mapping[str, Any]) -> Answer:
    """An answer from plain data; `ValueError` when it is not one."""
    kind = raw.get("type")
    if kind == "noul":
        return NoulAnswer(float(raw["probability"]))
    if kind == "choice":
        return ChoiceAnswer(
            str(raw["choice"]), None, {str(k): float(v) for k, v in raw["probabilities"].items()}
        )
    if kind == "score":
        return ScoreAnswer(
            float(raw["score"]), None, {str(k): float(v) for k, v in raw["probabilities"].items()}
        )
    message = "ответ — noul, choice или score"
    raise ValueError(message)
