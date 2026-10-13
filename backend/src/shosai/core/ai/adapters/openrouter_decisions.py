"""OpenRouter's Decisions API wire format, as pure functions (no network).

Facts from the API reference and the Jev tutorial (read on 2026-10-13):

- `POST /api/alpha/decisions` takes `model`, `state` (text or JSON) and `questions`, a map of
  named questions; each has `type`, `instructions` and `criteria`: a map of option name to
  description (`choice`), a list of levels, the lowest first (`score`), or `true` and
  `false` descriptions (`noul`)
- the answer is `{id, model, provider, answers, usage {input_tokens, output_tokens, cost}}`;
  `model` names the dated snapshot (`typesafe/jev-1.13-20260917`)
- a `choice` answer has `choice`, `confidence` and `probabilities` by option name; a `score`
  answer has `score` (0 is the first level), `confidence` and `probabilities` keyed `"0"`,
  `"1"`…; a `noul` answer has `noul`, a probability

The endpoint is alpha: any departure from this shape is a provider error, never a guess,
and the contract test on a recorded answer fails the release (Leo architecture §6.1).
"""

from collections.abc import Mapping
from typing import Final

from shosai.core.ai.adapters.http_calls import Json
from shosai.core.ai.adapters.openrouter_wire import reported_cost
from shosai.core.ai.calls import ModelRef
from shosai.core.ai.decisions import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    Decision,
    DecisionRequest,
    NoulAnswer,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.results import Usage

DECISIONS_PATH: Final = "../alpha/decisions"


def question_body(question: Question) -> Json:
    """One question in the API's shape."""
    if isinstance(question, ChoiceQuestion):
        return {"type": "choice", "instructions": question.instructions,
                "criteria": dict(question.criteria)}  # fmt: skip
    if isinstance(question, ScoreQuestion):
        return {"type": "score", "instructions": question.instructions,
                "criteria": list(question.criteria)}  # fmt: skip
    body: Json = {"type": "noul", "instructions": question.instructions}
    if question.when_true is not None and question.when_false is not None:
        body["criteria"] = {"true": question.when_true, "false": question.when_false}
    return body


def decision_body(model: str, request: DecisionRequest) -> Json:
    """The body of `/alpha/decisions`."""
    state = request.state if isinstance(request.state, str) else dict(request.state)
    questions = {name: question_body(q) for name, q in request.questions.items()}
    return {"model": model, "state": state, "questions": questions}


def broken() -> AiCallError:
    """The error of an answer that left the contract."""
    return AiCallError(AiFailure.PROVIDER_ERROR)


def probability(raw: object) -> float:
    """A number between 0 and 1."""
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not 0 <= raw <= 1:
        raise broken()
    return float(raw)


def probabilities(raw: object, keys: set[str]) -> Mapping[str, float]:
    """Probabilities keyed by the expected names only; absent is empty."""
    if raw is None:
        return {}
    if not isinstance(raw, dict) or not set(raw) <= keys:
        raise broken()
    return {str(key): probability(value) for key, value in raw.items()}


def confidence(raw: object) -> float | None:
    """The optional confidence of an answer."""
    return None if raw is None else probability(raw)


def answer_of(question: Question, raw: object) -> Answer:
    """The answer to one question, checked against what was asked."""
    if not isinstance(raw, dict):
        raise broken()
    kind = raw.get("type")
    if isinstance(question, ChoiceQuestion):
        options = set(question.criteria)
        if kind != "choice" or raw.get("choice") not in options:
            raise broken()
        return ChoiceAnswer(
            choice=str(raw["choice"]),
            confidence=confidence(raw.get("confidence")),
            probabilities=probabilities(raw.get("probabilities"), options),
        )
    if isinstance(question, ScoreQuestion):
        top = len(question.criteria) - 1
        score = raw.get("score")
        if kind != "score" or isinstance(score, bool) or not isinstance(score, int | float):
            raise broken()
        if not 0 <= score <= top:
            raise broken()
        return ScoreAnswer(
            score=float(score),
            confidence=confidence(raw.get("confidence")),
            probabilities=probabilities(raw.get("probabilities"), {str(i) for i in range(top + 1)}),
        )
    if kind != "noul":
        raise broken()
    return NoulAnswer(probability(raw.get("noul")))


def decision_usage(raw: object) -> Usage:
    """Input and output tokens and the cost OpenRouter charged."""
    if not isinstance(raw, dict):
        raise broken()
    tokens = raw.get("input_tokens"), raw.get("output_tokens")
    if not all(isinstance(count, int) and count >= 0 for count in tokens):
        raise broken()
    return Usage(
        input_tokens=int(raw["input_tokens"]),
        output_tokens=int(raw["output_tokens"]),
        reported_cost_usd=reported_cost(raw.get("cost")),
    )


def decision_of(answer: Json, model: ModelRef, request: DecisionRequest) -> Decision:
    """The decision of an answer; every question answered, each in its own type."""
    answers = answer.get("answers")
    snapshot = answer.get("model")
    if not isinstance(answers, dict) or set(answers) != set(request.questions):
        raise broken()
    if not isinstance(snapshot, str) or not snapshot:
        raise broken()
    decision_id = answer.get("id")
    return Decision(
        answers={name: answer_of(q, answers[name]) for name, q in request.questions.items()},
        model=model,
        snapshot=snapshot,
        decision_id=decision_id if isinstance(decision_id, str) else None,
        usage=decision_usage(answer.get("usage")),
    )
