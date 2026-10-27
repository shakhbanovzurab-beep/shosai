"""Fitting a cut for a target precision, its calibration error, and a record's state hash
(Leo §6.4, §6.5)."""

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.decisions.domain.calibration import (
    CutAim,
    accuracy,
    expected_calibration_error,
    fit_cut,
)
from shosai.features.decisions.domain.records import effect_key, state_hash
from shosai.features.decisions.domain.verdicts import Cut, Verdict

GOLDEN = 0.6180339887498949
SILVER = 0.4142135623730951
cases = st.lists(
    st.tuples(st.floats(min_value=0, max_value=1), st.booleans()), min_size=1, max_size=200
)
aims = st.builds(
    CutAim,
    side=st.sampled_from([Verdict.YES, Verdict.NO]),
    precision=st.floats(min_value=0.5, max_value=1),
    unsure_joins=st.sampled_from([Verdict.YES, Verdict.NO]),
)


def positive(cut: Cut, chance: float, joins: Verdict) -> bool:
    """Whether a case lands on the YES side once unsure joins its side."""
    verdict = cut.verdict(chance)
    return verdict is Verdict.YES or (verdict is Verdict.UNSURE and joins is Verdict.YES)


@given(cases, aims)
def test_a_fitted_cut_keeps_its_sides_precision(
    labelled: list[tuple[float, bool]], aim: CutAim
) -> None:
    cut = fit_cut(labelled, aim, margin=0.0)
    if cut is None:
        return
    wanted = aim.side is Verdict.YES
    kept = [
        label for chance, label in labelled if positive(cut, chance, aim.unsure_joins) is wanted
    ]
    assert kept
    assert sum(label is wanted for label in kept) / len(kept) >= aim.precision - 1e-9


def test_the_margin_falls_on_the_side_unsure_joins() -> None:
    labelled = [(i / 100, i >= 60) for i in range(100)]
    warn = fit_cut(labelled, CutAim(Verdict.YES, 1.0, unsure_joins=Verdict.YES), margin=0.05)
    trust = fit_cut(labelled, CutAim(Verdict.YES, 1.0, unsure_joins=Verdict.NO), margin=0.05)
    assert warn is not None
    assert trust is not None
    # Край исхода один и тот же — 0,60; «не уверен» ложится по разные стороны от него.
    assert (warn.lower, warn.upper) == pytest.approx((0.60, 0.70))
    assert (trust.lower, trust.upper) == pytest.approx((0.50, 0.60))
    assert positive(warn, 0.60, Verdict.YES)
    assert not positive(warn, 0.59, Verdict.YES)
    assert positive(trust, 0.60, Verdict.NO)
    assert not positive(trust, 0.59, Verdict.NO)


def test_no_cut_when_no_boundary_reaches_the_target() -> None:
    labelled = [(0.9, False), (0.8, False), (0.1, True)]
    assert fit_cut(labelled, CutAim(Verdict.YES, 0.9, unsure_joins=Verdict.NO), 0.05) is None


def test_equal_probabilities_never_split() -> None:
    labelled = [(0.7, True), (0.7, False), (0.7, True), (0.2, False)]
    cut = fit_cut(labelled, CutAim(Verdict.YES, 1.0, unsure_joins=Verdict.NO), margin=0.0)
    assert cut is None


def test_a_calibrated_model_has_almost_no_calibration_error() -> None:
    # Детерминированная равномерная последовательность вместо случайной: результат один и тот же.
    chances = [(i * GOLDEN) % 1 for i in range(20_000)]
    labelled = [(chance, ((i * SILVER) % 1) < chance) for i, chance in enumerate(chances)]
    assert expected_calibration_error(labelled) < 0.02
    overconfident = [(0.95, i % 2 == 0) for i in range(2_000)]
    assert expected_calibration_error(overconfident) > 0.4
    assert expected_calibration_error([]) == 0.0


def test_accuracy_is_the_share_that_agreed() -> None:
    assert accuracy([True, True, False, True]) == 0.75
    assert accuracy([]) == 0.0


def test_a_state_hash_is_keyed_and_short() -> None:
    first = state_hash('{"text":"hello"}', b"home-key")
    assert first == state_hash('{"text":"hello"}', b"home-key")
    assert first != state_hash('{"text":"hello"}', b"other-key")
    assert first != state_hash('{"text":"hellO"}', b"home-key")
    assert len(first) == 16
    with pytest.raises(ValueError, match="ключ"):
        state_hash("{}", b"")


def test_a_decisions_cost_row_has_its_own_effect_key() -> None:
    decision_id = uuid4()
    assert effect_key(decision_id) == f"decision:{decision_id}"
