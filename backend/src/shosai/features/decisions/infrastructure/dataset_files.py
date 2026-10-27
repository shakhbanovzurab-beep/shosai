"""Writing a point's sets: synthetic cases appended, the machine's labels on the reference, and
drafts a person labels blind (ADR 0069 DL-D8).

Synthetic cases are appended to their language's file with ids that continue it. The
machine's labels are written beside the person's on every reference case, never over them.
A draft for the reference is a case without labels, with the questions to answer — in
`reference/drafts/<language>.jsonl`, outside the sets until a person labels it and moves it
into `reference/<language>.jsonl`; it never shows the label the case was written for.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from shosai.features.decisions.domain.examples import Case, Label, case_data, facts_data
from shosai.features.decisions.domain.policy import Policy, question_text
from shosai.features.decisions.infrastructure.datasets import DATASETS, lines, point_folder

# Номера черновиков эталона — отдельно от синтетики, чтобы их id не совпадали.
DRAFT_OFFSET: Final = 50_000


def write_lines(path: Path, rows: Sequence[Mapping[str, Any]], *, append: bool) -> None:
    """JSON Lines, one object per line, appended or replacing the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    with path.open("a" if append else "w", encoding="utf-8") as file:
        file.write(text)


def synthetic_count(policy: Policy[Any, Any], language: str, root: Path = DATASETS) -> int:
    """How many synthetic cases a language already has: where the next ones start."""
    path = point_folder(policy.point, root) / "synthetic" / f"{language}.jsonl"
    return len(lines(path)) if path.exists() else 0


def draft_count(policy: Policy[Any, Any], language: str, root: Path = DATASETS) -> int:
    """How many drafts a language already has; drafts number apart from synthetic cases."""
    path = point_folder(policy.point, root) / "reference" / "drafts" / f"{language}.jsonl"
    return DRAFT_OFFSET + (len(lines(path)) if path.exists() else 0)


def append_synthetic(
    policy: Policy[Any, Any], language: str, cases: Sequence[Case], root: Path = DATASETS
) -> Path:
    """Append generated cases to their language's file."""
    path = point_folder(policy.point, root) / "synthetic" / f"{language}.jsonl"
    write_lines(path, [case_data(case) for case in cases], append=True)
    return path


def with_machine_labels(path: Path, labelled: Mapping[str, Mapping[str, Label]]) -> int:
    """Write the machine's labels beside the person's; how many cases got them."""
    rows = lines(path)
    for row in rows:
        machine = labelled.get(str(row.get("id")))
        if machine is not None:
            row["machine_labels"] = dict(machine)
    write_lines(path, rows, append=False)
    return sum(1 for row in rows if str(row.get("id")) in labelled)


def write_drafts(
    policy: Policy[Any, Any], language: str, cases: Sequence[Case], root: Path = DATASETS
) -> Path:
    """Drafts for a person to label: facts and questions, no labels."""
    path = point_folder(policy.point, root) / "reference" / "drafts" / f"{language}.jsonl"
    rows = [
        {
            "id": f"ref-{case.id}", "language": language, "facts": facts_data(case.facts),
            "questions": {
                name: question_text(question)
                for name, question in policy.questions(case.facts).items()
            },
            "labels": {},
        }
        for case in cases
    ]  # fmt: skip
    write_lines(path, rows, append=True)
    return path
