"""Whether a policy version may be released: its gates on synthetic and reference cases
(Leo §6.4, ADR 0069 DL-D8).

Cuts are fitted on the synthetic cases of all languages. A release then needs, on the
synthetic set:

- at least 50 cases on each side of each cut in each of the 16 languages,
- an expected calibration error of at most 0.05 per cut,
- an accuracy of the judged outcome at least the policy's floor in every language,

and on the reference set, labelled blind (`datasets/REFERENCE_LABELLING.md`):

- at least 50 cases in Russian and 50 in English,
- the machine's labels agreeing with the reference's on at least 90 % of the cases,
- in each language an accuracy at least the floor and no more than 10 points below the
  synthetic one,
- the careful outcome found in at least the policy's careful share of the cases that call
  for it.

A failed gate is named by a short code; the report keeps numbers only.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from shosai.core.ai.decisions import Answer
from shosai.features.decisions.domain.calibration import (
    ECE_GATE,
    accuracy,
    expected_calibration_error,
    fit_cut,
)
from shosai.features.decisions.domain.examples import Case, expected, truth
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.domain.verdicts import Cut, probability, read

SIDE_MINIMUM: Final = 50
REFERENCE_MINIMUM: Final = 50
REFERENCE_LANGUAGES: Final = ("ru", "en")
MACHINE_AGREEMENT: Final = 0.9
REFERENCE_GAP: Final = 0.10


@dataclass(frozen=True, slots=True)
class Answered:
    """A case and Jev's answers to its questions."""

    case: Case
    answers: Mapping[str, Answer]


@dataclass(frozen=True, slots=True)
class Report:
    """The fitted cuts, the failed gates and the numbers behind them."""

    cuts: Mapping[str, Cut]
    failures: tuple[str, ...]
    numbers: Mapping[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Every gate held."""
        return not self.failures


def calibrated(
    policy: Policy[Any, Any],
    synthetic: Sequence[Answered],
    reference: Sequence[Answered],
    languages: Sequence[str],
) -> Report:
    """Fit the cuts on the synthetic cases and check every gate."""
    failures: list[str] = []
    numbers: dict[str, Any] = {"cases": len(synthetic), "reference_cases": len(reference)}
    pairs = labelled_pairs(policy, synthetic)
    cuts: dict[str, Cut] = {}
    for name in policy.cuts:
        cut = fit_cut(pairs[name], policy.aims.cuts[name], policy.aims.margin)
        if cut is None:
            failures.append(f"fit:{name}")
        else:
            cuts[name] = cut
    failures += side_counts(policy, synthetic, languages, numbers)
    numbers["ece"] = {
        name: round(expected_calibration_error(pairs[name]), 4) for name in policy.cuts
    }
    failures += [f"ece:{name}" for name, ece in numbers["ece"].items() if ece > ECE_GATE]
    if len(cuts) == len(policy.cuts):
        failures += judged_gates(policy, cuts, (synthetic, reference), languages, numbers)
    return Report(cuts, tuple(failures), numbers)


def labelled_pairs(
    policy: Policy[Any, Any], cases: Sequence[Answered]
) -> dict[str, list[tuple[float, bool]]]:
    """(probability, truth) of every answered question, by the cut it is read through."""
    pairs: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for item in cases:
        for name, signal in policy.signals(item.case.facts).items():
            answer = item.answers.get(name)
            if answer is not None:
                pairs[signal.cut].append(
                    (probability(answer, signal), truth(signal, item.case.labels[name]))
                )
    return pairs


def side_counts(
    policy: Policy[Any, Any],
    cases: Sequence[Answered],
    languages: Sequence[str],
    numbers: dict[str, Any],
) -> list[str]:
    """At least 50 cases on each side of each cut in every language."""
    counts: Counter[tuple[str, str, bool]] = Counter()
    for item in cases:
        for name, signal in policy.signals(item.case.facts).items():
            counts[item.case.language, signal.cut, truth(signal, item.case.labels[name])] += 1
    numbers["counts"] = {
        language: {cut: {"yes": counts[language, cut, True], "no": counts[language, cut, False]}
                   for cut in policy.cuts}
        for language in languages
    }  # fmt: skip
    return [
        f"count:{language}:{cut}:{'yes' if side else 'no'}"
        for language in languages
        for cut in policy.cuts
        for side in (True, False)
        if counts[language, cut, side] < SIDE_MINIMUM
    ]


def judged_gates(
    policy: Policy[Any, Any],
    cuts: Mapping[str, Cut],
    sets: tuple[Sequence[Answered], Sequence[Answered]],
    languages: Sequence[str],
    numbers: dict[str, Any],
) -> list[str]:
    """Accuracy per language, then the reference's gates."""
    synthetic, reference = sets
    floor = policy.aims.accuracy_floor
    seen = per_language(policy, cuts, synthetic)
    numbers["accuracy"] = {language: rate(seen.get(language, [])) for language in languages}
    failures = [f"accuracy:{lang}" for lang, value in numbers["accuracy"].items() if value < floor]
    return failures + reference_gates(policy, cuts, reference, numbers)


def reference_gates(
    policy: Policy[Any, Any],
    cuts: Mapping[str, Cut],
    reference: Sequence[Answered],
    numbers: dict[str, Any],
) -> list[str]:
    """The reference set: its size, the machine's agreement, accuracy, the careful outcome."""
    failures: list[str] = []
    sizes = Counter(item.case.language for item in reference)
    failures += [
        f"reference_count:{language}"
        for language in REFERENCE_LANGUAGES
        if sizes[language] < REFERENCE_MINIMUM
    ]
    agreed = [
        bool(i.case.machine_labels) and i.case.machine_labels == i.case.labels for i in reference
    ]
    numbers["agreement"] = rate(agreed)
    if numbers["agreement"] < MACHINE_AGREEMENT:
        failures.append("agreement")
    seen = per_language(policy, cuts, reference)
    careful = per_language(policy, cuts, reference, careful_only=True)
    numbers["reference_accuracy"], numbers["careful"] = {}, {}
    for language in REFERENCE_LANGUAGES:
        value = rate(seen.get(language, []))
        numbers["reference_accuracy"][language] = value
        numbers["careful"][language] = rate(careful.get(language, []))
        synthetic = numbers["accuracy"].get(language, 0.0)
        if value < policy.aims.accuracy_floor:
            failures.append(f"reference_accuracy:{language}")
        if value < synthetic - REFERENCE_GAP:
            failures.append(f"reference_gap:{language}")
        if numbers["careful"][language] < policy.aims.careful:
            failures.append(f"careful:{language}")
    return failures


def per_language(
    policy: Policy[Any, Any],
    cuts: Mapping[str, Cut],
    cases: Sequence[Answered],
    *,
    careful_only: bool = False,
) -> dict[str, list[bool]]:
    """Whether each case's judged outcome agrees with its expected one, by language."""
    agreements: dict[str, list[bool]] = defaultdict(list)
    for item in cases:
        wanted = expected(policy, item.case)
        if careful_only and not policy.careful_case(wanted):
            continue
        verdicts, chances = read(item.answers, policy.signals(item.case.facts), cuts)
        judged = policy.outcome(item.case.facts, verdicts, chances)
        agreements[item.case.language].append(policy.agrees(judged, wanted))
    return agreements


def rate(agreements: Sequence[bool]) -> float:
    """The share that agreed, rounded for the report."""
    return round(accuracy(agreements), 4)
