"""A donated case replayed against today's model and judged against the rated answer (step 11c)."""

import uuid

import pytest

from shosai.composition.agent_cases_command import report_of
from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatResult
from shosai.features.agent.application.case_replay import (
    CaseReplay,
    CaseScore,
    StoredCase,
    Verdict,
    verdict_of,
)
from shosai.features.agent.application.run_context import text_of
from shosai.features.agent.domain.feedback import Rating
from shosai.features.agent.infrastructure.prompts import POLICY
from tests.features.agent.turn_doubles import Utility

ROUTE = ModelRoute(ModelRef(Provider.OPENROUTER, "standard-model"))
CASE = {
    "question": "What did [name] agree with Northwind?",
    "rounds": [{"text": "", "calls": [], "results": [{"tool": "notes.search", "digest": "€18."}]}],
    "sources": [],
    "answer": "I don't know.",
}


def stored(rating: Rating) -> StoredCase:
    return StoredCase(uuid.uuid4(), rating, "de", CASE)


async def test_the_replay_answers_from_the_kept_results_and_the_judge_compares() -> None:
    model = Utility(["€18 per seat.", '{"verdict": "better", "reason": "Grounded now."}'])

    score = await CaseReplay(model, (ROUTE, ROUTE)).score(stored(Rating.NOT_USEFUL))

    asked, judged = model.requests
    head = text_of(asked.messages[0])
    assert POLICY in head
    assert "notes.search: €18." in head
    assert "(Deutsch)" in head
    assert text_of(asked.messages[1]) == CASE["question"]
    assert "rated not useful" in text_of(judged.messages[1])
    assert "€18 per seat." in text_of(judged.messages[1])
    assert (score.verdict, score.passed) == (Verdict.BETTER, True)


@pytest.mark.parametrize(
    ("rating", "verdict", "passed"),
    [
        (Rating.USEFUL, Verdict.SAME, True),
        (Rating.USEFUL, Verdict.WORSE, False),
        (Rating.NOT_USEFUL, Verdict.SAME, False),
        (Rating.USEFUL, None, None),
    ],
)
def test_a_useful_case_guards_and_a_not_useful_one_must_improve(
    rating: Rating, verdict: Verdict | None, *, passed: bool | None
) -> None:
    assert CaseScore(uuid.uuid4(), rating, "en", verdict).passed is passed


def test_only_the_judge_s_json_is_a_verdict() -> None:
    assert verdict_of('Sure: {"verdict": "same", "reason": "Equal."}') is Verdict.SAME
    assert verdict_of('{"verdict": "great", "reason": "?"}') is None
    assert verdict_of('{"verdict": 1, "reason": "?"}') is None
    assert verdict_of("no json") is None


class Silent:
    """A model that never answers."""

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        del context, route, request
        raise AiCallError(AiFailure.MODEL_UNAVAILABLE)


async def test_a_model_that_fails_leaves_the_case_ungraded() -> None:
    score = await CaseReplay(Silent(), (ROUTE, ROUTE)).score(stored(Rating.USEFUL))

    assert (score.verdict, score.passed) == (None, None)


def test_the_report_keeps_scores_only() -> None:
    scores = [
        CaseScore(uuid.uuid4(), Rating.USEFUL, "en", Verdict.WORSE),
        CaseScore(uuid.uuid4(), Rating.NOT_USEFUL, "ru", Verdict.BETTER),
        CaseScore(uuid.uuid4(), Rating.NOT_USEFUL, "ru", None),
    ]

    report = report_of(scores)

    assert report["results"] == {
        "not_useful:true": 1, "not_useful:ungraded": 1, "useful:false": 1,
    }  # fmt: skip
    assert report["guard_broken"] == 1
    assert "Northwind" not in str(report)
    assert "€" not in str(report)
