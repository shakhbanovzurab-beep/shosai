"""Writing a point's sets: synthetic cases appended, the machine's labels on the reference, and
drafts labelled blind (ADR 0069 DL-D8).

Synthetic cases are appended to their language's file with ids that continue its highest. The
machine's labels are written beside the reference's on every case, never over them.
A draft for the reference is a case without labels, with the questions to answer — in
`reference/drafts/<language>.jsonl`, outside the sets until it is labelled and moved
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


def next_number(path: Path, first: int = 0) -> int:
    """The number after the highest a file's ids end with, or `first` for a new file: the
    labeller drops cases between kept ones, so a count would hand out a kept id again."""
    numbers = (
        [int(str(row["id"]).rsplit("-", 1)[1]) for row in lines(path)] if path.exists() else []
    )
    return max(numbers, default=first - 1) + 1


def next_synthetic(policy: Policy[Any, Any], language: str, root: Path = DATASETS) -> int:
    """Where a language's next synthetic cases start."""
    return next_number(point_folder(policy.point, root) / "synthetic" / f"{language}.jsonl")


def next_draft(policy: Policy[Any, Any], language: str, root: Path = DATASETS) -> int:
    """Where a language's next drafts start; drafts number apart from synthetic cases."""
    path = point_folder(policy.point, root) / "reference" / "drafts" / f"{language}.jsonl"
    return next_number(path, DRAFT_OFFSET)


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
