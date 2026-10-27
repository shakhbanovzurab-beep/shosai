"""Made-up labelled sets for the friction policy and Jev's answers to them, for the gates' tests.

Labels alternate deterministically; answers lean the labelled way by a set amount, so a test
chooses how well calibrated, and how separable, the answers are.
"""

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from shosai.core.agent_tools.spec import Reversibility
from shosai.core.ai.decisions import Answer, NoulAnswer, ScoreAnswer
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.decisions.domain.examples import Case, Label
from shosai.features.decisions.domain.gates import Answered
from shosai.features.decisions.domain.policies.action_friction import CardFacts

FACTS = CardFacts(
    tool="tasks.create", toolset="tasks", reversibility=Reversibility.REVERSIBLE, items=2,
    other_space=False, rounds=1, request="Create two tasks for tomorrow", card="Create tasks",
)  # fmt: skip


def facts_of(case_id: str) -> CardFacts:
    """The card of one case: its request names the case, so a double can tell cases apart."""
    return replace(FACTS, request=f"case {case_id}")


def facts_json(facts: CardFacts) -> dict[str, Any]:
    """A card's facts as a dataset line holds them."""
    return {
        "tool": facts.tool, "toolset": facts.toolset,
        "reversibility": facts.reversibility.value, "items": facts.items,
        "other_space": facts.other_space, "rounds": facts.rounds, "request": facts.request,
        "card": facts.card,
    }  # fmt: skip


def index_of(request: str) -> int:
    """The case's number from its request."""
    return int(request.rsplit("-", 1)[1])


def labels_of(index: int) -> dict[str, Label]:
    """Half the cases match the request, a third reach wide; the two vary independently."""
    return {"matches_request": index % 2 == 0, "reach": 3 if index % 3 == 0 else 0}


def answers_for(labels: Mapping[str, Label], *, lean: float, index: int) -> dict[str, Answer]:
    """Answers leaning `lean` towards the labels, with a small spread per case."""
    spread = (index % 5) * 0.01
    matches = 0.5 + lean - spread if labels["matches_request"] else 0.5 - lean + spread
    wide = 0.5 + lean - spread if labels["reach"] == 3 else 0.5 - lean + spread
    levels = {"0": 1 - wide, "1": 0.0, "2": 0.0, "3": wide}
    return {
        "matches_request": NoulAnswer(round(matches, 4)),
        "reach": ScoreAnswer(3 * wide, None, levels),
    }


def friction_sets(
    per_language: int = 160, reference: int = 60, *, lean: float = 0.49
) -> tuple[list[Answered], list[Answered]]:
    """Synthetic cases in the 16 languages and a reference in Russian and English, answered."""
    synthetic = [
        Answered(
            Case(f"{lang}-{i}", lang, facts_of(f"{lang}-{i}"), labels_of(i)),
            answers_for(labels_of(i), lean=lean, index=i),
        )
        for lang in SUPPORTED_LANGUAGES
        for i in range(per_language)
    ]
    people = [
        Answered(
            Case(
                f"ref-{lang}-{i}",
                lang,
                facts_of(f"ref-{lang}-{i}"),
                labels_of(i),
                machine_labels=labels_of(i),
            ),
            answers_for(labels_of(i), lean=lean, index=i),
        )
        for lang in ("ru", "en")
        for i in range(reference)
    ]
    return synthetic, people


def write_sets(root: Path, synthetic: list[Answered], reference: list[Answered]) -> None:
    """Write sets as a point's folder holds them (without the recorded run)."""
    folder = root / "action_friction"
    for kind, cases in (("synthetic", synthetic), ("reference", reference)):
        by_language: dict[str, list[str]] = {}
        for item in cases:
            line: dict[str, Any] = {
                "id": item.case.id, "language": item.case.language,
                "facts": facts_json(item.case.facts),
                "labels": dict(item.case.labels),
            }  # fmt: skip
            if item.case.machine_labels:
                line["machine_labels"] = dict(item.case.machine_labels)
            by_language.setdefault(item.case.language, []).append(json.dumps(line))
        (folder / kind).mkdir(parents=True, exist_ok=True)
        for language, rows in by_language.items():
            (folder / kind / f"{language}.jsonl").write_text(
                "\n".join(rows) + "\n", encoding="utf-8"
            )
