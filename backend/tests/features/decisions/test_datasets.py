"""The committed sets hold their gates in CI, without a call; a set out of shape is refused
(decisions plan §3.5, ADR 0069 DL-D8)."""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from shosai.composition.decisions_command import (
    DecisionsCommand,
    decisions_command,
    run_decisions,
)
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.entrypoints.cli import build_parser
from shosai.features.decisions.domain.gates import calibrated
from shosai.features.decisions.domain.policies import POLICIES
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.infrastructure.datasets import (
    DATASETS,
    answered,
    point_folder,
    read_recorded,
    read_report,
    read_sets,
    report_data,
)
from tests.features.decisions.sets_bench import facts_json, facts_of


@pytest.mark.parametrize("policy", POLICIES, ids=lambda policy: policy.key)
def test_a_committed_set_is_answered_and_its_report_is_its_run_s(policy: Policy[Any, Any]) -> None:
    if not point_folder(policy.point).exists():
        pytest.skip("this point has no set yet: its policy cannot be promoted")
    sets = read_sets(policy)
    recorded = read_recorded(policy)

    report = calibrated(
        policy,
        answered(sets.synthetic, recorded),
        answered(sets.reference, recorded),
        SUPPORTED_LANGUAGES,
    )

    assert len(recorded) == len(sets.synthetic) + len(sets.reference)
    assert read_report(policy) == report_data(policy, report)


def case_line(case_id: str, language: str, **change: object) -> str:
    """One case of the friction policy as a dataset line."""
    line = {
        "id": case_id, "language": language, "facts": facts_json(facts_of(case_id)),
        "labels": {"matches_request": True, "reach": 0},
    } | change  # fmt: skip
    return json.dumps(line)


@pytest.mark.parametrize(
    ("file", "line", "words"),
    [
        ("xx.jsonl", case_line("xx-1", "xx"), "языков"),
        ("ru.jsonl", case_line("en-1", "en"), "другом языке"),
        (
            "ru.jsonl",
            case_line("ru-1", "ru", labels={"matches_request": "yes", "reach": 0}),
            "метка",
        ),
        ("ru.jsonl", case_line("ru-1", "ru", labels={"matches_request": True}), "метки"),
        ("ru.jsonl", case_line("ru-1", "ru", facts={"tool": 3}), "поле"),
        ("ru.jsonl", f"{case_line('ru-1', 'ru')}\n{case_line('ru-1', 'ru')}", "повторяются"),
    ],
)
def test_a_set_out_of_shape_is_refused_with_the_reason(
    tmp_path: Path, file: str, line: str, words: str
) -> None:
    folder = tmp_path / "action_friction" / "synthetic"
    folder.mkdir(parents=True)
    (folder / file).write_text(line + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=words):
        read_sets(ACTION_FRICTION, tmp_path)


async def test_the_check_reads_every_points_sets() -> None:
    out = io.StringIO()

    code = await run_decisions({}, DecisionsCommand(action="check"), out)

    assert code == 0
    assert {line.split(":")[0] for line in out.getvalue().splitlines()} == {
        policy.key for policy in POLICIES
    }
    assert DATASETS.name == "datasets"


@pytest.mark.parametrize(
    ("argv", "command"),
    [
        (["decisions", "dataset", "check"], DecisionsCommand(action="check")),
        (
            [
                "decisions",
                "dataset",
                "generate",
                "turn.route@1",
                "--language",
                "all",
                "--count",
                "8",
            ],
            DecisionsCommand(action="generate", target="turn.route@1", language="all", count=8),
        ),
        (
            [
                "decisions",
                "dataset",
                "draft-reference",
                "turn.route@1",
                "--language",
                "ru",
                "--count",
                "60",
            ],
            DecisionsCommand(action="draft", target="turn.route@1", language="ru", count=60),
        ),
        (
            ["decisions", "dataset", "label-reference", "turn.route@1"],
            DecisionsCommand(action="label", target="turn.route@1"),
        ),
        (
            ["decisions", "calibrate", "action.friction@1", "--recorded"],
            DecisionsCommand(action="calibrate", target="action.friction@1", recorded=True),
        ),
        (
            ["decisions", "promote", "turn.route@1", "--revision", "3", "--to", "shadow"],
            DecisionsCommand(action="promote", target="turn.route@1", revision=3, state="shadow"),
        ),
        (
            ["decisions", "retire", "turn.route@1", "--note", "rules"],
            DecisionsCommand(action="retire", target="turn.route@1", note="rules"),
        ),
    ],
)
def test_the_command_line_names_the_action(argv: list[str], command: DecisionsCommand) -> None:
    assert decisions_command(build_parser().parse_args(argv)) == command
