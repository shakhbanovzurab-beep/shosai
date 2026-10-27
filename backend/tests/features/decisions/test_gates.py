"""A version's release gates on synthetic and reference cases (Leo §6.4, ADR 0069 DL-D8)."""

from dataclasses import replace

from shosai.core.ai.decisions import NoulAnswer
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.decisions.domain.gates import Answered, calibrated
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from tests.features.decisions.sets_bench import friction_sets


def test_well_answered_sets_pass_every_gate() -> None:
    synthetic, reference = friction_sets()

    report = calibrated(ACTION_FRICTION, synthetic, reference, SUPPORTED_LANGUAGES)

    assert report.failures == ()
    assert set(report.cuts) == {"matches", "wide"}
    assert all(value <= 0.05 for value in report.numbers["ece"].values())
    assert set(report.numbers["accuracy"]) == set(SUPPORTED_LANGUAGES)
    assert report.numbers["agreement"] == 1.0


def test_a_language_short_of_cases_fails_its_count() -> None:
    synthetic, reference = friction_sets()
    short = [item for item in synthetic if item.case.language != "ja" or item.case.id < "ja-2"]

    report = calibrated(ACTION_FRICTION, short, reference, SUPPORTED_LANGUAGES)

    assert "count:ja:wide:yes" in report.failures


def test_answers_that_overstate_fail_the_calibration_error() -> None:
    synthetic, reference = friction_sets(lean=0.3)

    report = calibrated(ACTION_FRICTION, synthetic, reference, SUPPORTED_LANGUAGES)

    assert {"ece:matches", "ece:wide"} <= set(report.failures)


def test_the_machine_disagreeing_with_the_person_fails_the_reference() -> None:
    synthetic, reference = friction_sets()
    flipped = [
        Answered(replace(item.case, machine_labels={**item.case.labels, "reach": 1}), item.answers)
        for item in reference[:20]
    ]

    report = calibrated(ACTION_FRICTION, synthetic, flipped + reference[20:], SUPPORTED_LANGUAGES)

    assert report.numbers["agreement"] < 0.9
    assert "agreement" in report.failures


def test_a_reference_the_policy_misjudges_fails_its_accuracy_and_gap() -> None:
    synthetic, reference = friction_sets()
    # Ответы на эталон говорят «совпадает», хотя человек отметил обратное: политика промахнётся.
    misread = [
        Answered(item.case, {**item.answers, "matches_request": NoulAnswer(0.99)})
        for item in reference
    ]

    report = calibrated(ACTION_FRICTION, synthetic, misread, SUPPORTED_LANGUAGES)

    assert {"reference_accuracy:ru", "reference_gap:ru", "careful:ru"} <= set(report.failures)


def test_a_small_reference_fails_its_size() -> None:
    synthetic, reference = friction_sets(reference=30)

    report = calibrated(ACTION_FRICTION, synthetic, reference, SUPPORTED_LANGUAGES)

    assert {"reference_count:ru", "reference_count:en"} <= set(report.failures)


def test_without_a_cut_reaching_its_precision_the_fit_fails() -> None:
    synthetic, reference = friction_sets()
    # «Совпадает» с вероятностью ровно 0,5 у всех: ни одна граница не даёт точности 0,9.
    flat = [
        Answered(item.case, {**item.answers, "matches_request": NoulAnswer(0.5)})
        for item in synthetic
    ]

    report = calibrated(ACTION_FRICTION, flat, reference, SUPPORTED_LANGUAGES)

    assert "fit:matches" in report.failures
    assert not report.passed
