"""The curve that turns Jev's probability into a calibrated one: its isotonic fit, its reading,
the calibration error measured without grading itself, and how a revision stores it (the
owner's amendment of ADR 0069, 2026-10-27)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.ai.decisions import NoulAnswer
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.decisions.domain.calibration import (
    cross_fitted,
    expected_calibration_error,
    fit_curve,
)
from shosai.features.decisions.domain.gates import calibrated
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.domain.verdicts import Cut, Signal, on_curve, read
from shosai.features.decisions.infrastructure.policy_store import cuts_json, parsed_cuts
from tests.features.decisions.sets_bench import friction_sets

cases = st.lists(
    st.tuples(st.floats(min_value=0, max_value=1), st.booleans()), min_size=1, max_size=200
)


def test_the_curve_is_the_isotonic_fit() -> None:
    labelled = [(0.2, False), (0.2, True), (0.4, False), (0.5, True), (0.8, False), (0.9, True)]

    curve = fit_curve(labelled)

    assert curve == ((0.2, 1 / 3), (0.4, 1 / 3), (0.5, 0.5), (0.8, 0.5), (0.9, 1.0))
    assert on_curve(curve, 0.45) == pytest.approx(5 / 12)
    assert (on_curve(curve, 0.0), on_curve(curve, 1.0), on_curve((), 0.37)) == (1 / 3, 1.0, 0.37)


@given(cases)
def test_any_fitted_curve_is_a_valid_monotone_map(labelled: list[tuple[float, bool]]) -> None:
    curve = fit_curve(labelled)
    cut = Cut(lower=0.4, upper=0.6, curve=curve)

    points = sorted({chance for chance, _ in labelled})
    read_back = [cut.calibrated(chance) for chance in points]

    assert read_back == sorted(read_back)
    assert all(0 <= value <= 1 for value in read_back)


def test_a_curve_never_grades_itself() -> None:
    # Одна пятая случаев значит обратное: кривая, подогнанная без неё, на ней ошибается.
    labelled = [(0.9, index % 5 == 0) for index in range(500)]

    in_sample = [(on_curve(fit_curve(labelled), chance), t) for chance, t in labelled]

    assert expected_calibration_error(in_sample) == pytest.approx(0)
    assert expected_calibration_error(cross_fitted(labelled)) > 0.05


def test_answers_that_overstate_are_read_through_a_curve() -> None:
    synthetic, reference = friction_sets(lean=0.3)

    report = calibrated(ACTION_FRICTION, synthetic, reference, SUPPORTED_LANGUAGES)

    assert all(report.numbers["ece_raw"][name] > 0.05 for name in ("matches", "wide"))
    assert all(report.numbers["ece"][name] <= 0.05 for name in ("matches", "wide"))
    assert all(report.cuts[name].curve for name in ("matches", "wide"))


def test_a_verdict_reads_the_calibrated_probability() -> None:
    cuts = {"c": Cut(lower=0.5, upper=0.5, curve=((0.0, 0.0), (0.9, 0.4), (1.0, 1.0)))}

    verdicts, chances = read({"q": NoulAnswer(0.9)}, {"q": Signal("c")}, cuts)

    assert (verdicts["q"].value, chances["q"]) == ("no", 0.4)


def test_a_revision_keeps_its_curve_and_one_from_before_curves_has_none() -> None:
    cuts = {"c": Cut(lower=0.2, upper=0.3, curve=((0.1, 0.0), (0.9, 0.95)))}

    assert parsed_cuts(cuts_json(cuts)) == cuts
    assert parsed_cuts({"c": {"lower": 0.2, "upper": 0.3}}) == {"c": Cut(0.2, 0.3)}
    assert (
        parsed_cuts({"c": {"lower": 0.2, "upper": 0.3, "curve": [[0.9, 0.1], [0.1, 0.2]]}}) is None
    )
