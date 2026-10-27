"""The labelled sets and recorded runs, as files beside the code (decisions plan §3.5, DL-D8).

Each point has a folder named after it (`action_friction/`):

- `synthetic/<language>.jsonl` — generated cases, one language per file;
- `reference/ru.jsonl`, `reference/en.jsonl` — cases a person labelled, with the machine's
  labels beside the person's;
- `recorded.jsonl` — Jev's answers to every case, keyed by the case and the policy's wording,
  so CI re-reads them exactly without a call and a reworded policy never reuses them.

None of them holds a person's data: the cases are written for the purpose.
"""

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from shosai.core.ai.decisions import Answer
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.decisions.domain.examples import Case, answer_json, answer_of, parsed_case
from shosai.features.decisions.domain.gates import Answered
from shosai.features.decisions.domain.policy import Policy

DATASETS: Final = Path(__file__).parent / "datasets"
RECORDED: Final = "recorded.jsonl"


@dataclass(frozen=True, slots=True)
class PointSets:
    """A point's cases: synthetic and reference."""

    synthetic: tuple[Case, ...]
    reference: tuple[Case, ...]


def point_folder(point: str, root: Path = DATASETS) -> Path:
    """The folder of a point's sets."""
    return root / point.replace(".", "_")


def lines(path: Path) -> list[dict[str, Any]]:
    """The JSON objects of a JSON Lines file; `ValueError` names the line that is not one."""
    found: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            message = f"{path.name}:{number}: строка — не объект"
            raise ValueError(message)
        found.append(value)
    return found


def read_sets(policy: Policy[Any, Any], root: Path = DATASETS) -> PointSets:
    """A point's synthetic and reference cases; `ValueError` on any case out of shape."""
    folder = point_folder(policy.point, root)
    synthetic = read_cases(policy, sorted((folder / "synthetic").glob("*.jsonl")))
    reference = read_cases(policy, sorted((folder / "reference").glob("*.jsonl")))
    return PointSets(synthetic, reference)


def read_cases(policy: Policy[Any, Any], paths: Iterable[Path]) -> tuple[Case, ...]:
    """Cases of the files, each in its file's language, ids unique."""
    cases: list[Case] = []
    for path in paths:
        language = path.stem
        if language not in SUPPORTED_LANGUAGES:
            message = f"{path.name}: язык не из 16 языков платформы"
            raise ValueError(message)
        for raw in lines(path):
            case = parsed_case(policy, raw)
            if case.language != language:
                message = f"{path.name}: случай {case.id} на другом языке"
                raise ValueError(message)
            cases.append(case)
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        message = f"{policy.point}: id случаев повторяются"
        raise ValueError(message)
    return tuple(cases)


def read_recorded(
    policy: Policy[Any, Any], root: Path = DATASETS
) -> dict[str, Mapping[str, Answer]]:
    """Jev's recorded answers for this wording, by case; empty when there is no run."""
    path = point_folder(policy.point, root) / RECORDED
    if not path.exists():
        return {}
    digest = policy.digest()
    recorded: dict[str, Mapping[str, Answer]] = {}
    for raw in lines(path):
        if raw.get("digest") == digest:
            answers = raw.get("answers")
            if not isinstance(answers, dict):
                message = f"{RECORDED}: ответы случая {raw.get('id')} — не объект"
                raise ValueError(message)
            recorded[str(raw["id"])] = {name: answer_of(value) for name, value in answers.items()}
    return recorded


def write_recorded(
    policy: Policy[Any, Any],
    snapshot: str,
    answers: Mapping[str, Mapping[str, Answer]],
    root: Path = DATASETS,
) -> Path:
    """Write a run's answers for this wording, replacing the last run."""
    path = point_folder(policy.point, root) / RECORDED
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = policy.digest()
    rows = (
        json.dumps(
            {"id": case_id, "digest": digest, "snapshot": snapshot,
             "answers": {name: answer_json(answer) for name, answer in given.items()}},
            ensure_ascii=False, sort_keys=True,
        )
        for case_id, given in sorted(answers.items())
    )  # fmt: skip
    path.write_text("".join(f"{row}\n" for row in rows), encoding="utf-8")
    return path


def answered(cases: Sequence[Case], recorded: Mapping[str, Mapping[str, Answer]]) -> list[Answered]:
    """The cases that have answers, with them."""
    return [Answered(case, recorded[case.id]) for case in cases if case.id in recorded]
