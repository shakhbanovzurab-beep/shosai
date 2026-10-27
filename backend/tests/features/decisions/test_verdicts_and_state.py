"""Verdicts read through cuts with margins, and a state that never leaves its budget (Leo §6.1)."""

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.ai.decisions import ChoiceAnswer, NoulAnswer, ScoreAnswer
from shosai.features.decisions.domain.state import (
    BYTES_PER_TOKEN,
    TextField,
    build_state,
    clip,
    escaped_size,
    state_json,
    state_tokens,
)
from shosai.features.decisions.domain.verdicts import Cut, Signal, Verdict, probability, read

ORDER = {Verdict.NO: 0, Verdict.UNSURE: 1, Verdict.YES: 2}
chances = st.floats(min_value=0, max_value=1)
cuts = st.tuples(chances, st.floats(min_value=0, max_value=1)).map(
    lambda edges: Cut(lower=edges[0] * (1 - edges[1]), upper=edges[0])
)
# Тексты с тем, что JSON экранирует, и с одиночными суррогатами.
texts = st.text(max_size=3_000) | st.text(alphabet='"\\\n\t\x00\x01\ud800ab я', max_size=3_000)


@given(cuts, chances, chances)
def test_a_verdict_never_falls_as_the_probability_rises(cut: Cut, low: float, high: float) -> None:
    low, high = sorted((low, high))
    assert ORDER[cut.verdict(low)] <= ORDER[cut.verdict(high)]


@given(cuts, chances)
def test_inside_the_band_a_verdict_is_unsure(cut: Cut, chance: float) -> None:
    inside = cut.lower <= chance < cut.upper
    assert (cut.verdict(chance) is Verdict.UNSURE) is inside


@pytest.mark.parametrize(("lower", "upper"), [(0.2, 1.2), (0.6, 0.5), (-0.1, 0.3)])
def test_a_cut_outside_its_range_is_refused(lower: float, upper: float) -> None:
    with pytest.raises(ValueError, match="порог"):
        Cut(lower=lower, upper=upper)


def test_each_answer_gives_its_signal() -> None:
    assert probability(NoulAnswer(0.3), Signal("x")) == 0.3
    choice = ChoiceAnswer("b", None, {"a": 0.2, "b": 0.7, "c": 0.1})
    assert probability(choice, Signal("x", option="a")) == 0.2
    assert probability(ChoiceAnswer("b", None, {}), Signal("x", option="b")) == 1.0
    score = ScoreAnswer(1.6, None, {"0": 0.1, "1": 0.3, "2": 0.4, "3": 0.2})
    assert probability(score, Signal("x", at_least=2)) == pytest.approx(0.6)
    assert probability(ScoreAnswer(2.0, None, {}), Signal("x", at_least=2)) == 1.0
    with pytest.raises(ValueError, match="уровень"):
        probability(score, Signal("x"))


def test_an_unanswered_question_is_unsure() -> None:
    verdicts, chances_seen = read(
        {"a": NoulAnswer(0.9)},
        {"a": Signal("c"), "b": Signal("c")},
        {"c": Cut(lower=0.45, upper=0.55)},
    )
    assert verdicts == {"a": Verdict.YES, "b": Verdict.UNSURE}
    assert chances_seen == {"a": 0.9}


@given(texts, st.integers(min_value=1, max_value=700))
def test_a_clipped_text_fits_its_share_as_json_writes_it(text: str, tokens: int) -> None:
    clipped = clip(text, tokens)
    assert escaped_size(clipped) <= max(tokens * BYTES_PER_TOKEN, escaped_size("\n[...]\n"))
    assert escaped_size(clipped) == len(json.dumps(clipped, ensure_ascii=False).encode()) - 2


def test_a_long_text_keeps_its_head_and_its_tail() -> None:
    text = "start " + "middle " * 2_000 + " end"
    clipped = clip(text, 100)
    assert clipped.startswith("start ")
    assert clipped.endswith(" end")
    assert "[...]" in clipped


@given(texts, texts)
def test_a_state_stays_within_its_budget(request: str, card: str) -> None:
    state = build_state(
        {"tool": "tasks.create", "items": 3},
        {"request": TextField(request, 600), "card": TextField(card, 500)},
    )
    assert state_tokens(state) <= 2_000
    assert set(state) == {"facts", "request", "card"}
    state_json(state).encode()


def test_a_text_field_cannot_take_the_facts_name() -> None:
    with pytest.raises(ValueError, match="facts"):
        build_state({}, {"facts": TextField("x", 10)})


def test_a_state_over_its_budget_is_refused() -> None:
    with pytest.raises(ValueError, match="бюджет"):
        build_state({}, {"text": TextField("слово " * 5_000, 3_000)}, budget=2_000)
