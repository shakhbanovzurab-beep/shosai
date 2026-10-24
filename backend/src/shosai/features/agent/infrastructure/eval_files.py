"""The evaluation's data shipped with the slice, and the reports a live run writes (AG-D8).

Scenarios, the injection corpus and the baselines live in `eval_data/` beside this module and
are read from the installed package. A run's report is a directory of its own: `report.json`
with every case, `report.md` for the change's record, and — when the run was asked to record
one — the new baseline to copy into `eval_data/`.
"""

import json
from dataclasses import asdict
from importlib.resources import files  # nosemgrep
from pathlib import Path
from typing import Final

from shosai.features.agent.domain.eval_cases import EvalScenario, EvalScenarios, InjectionCorpus
from shosai.features.agent.domain.eval_checks import CostLine
from shosai.features.agent.domain.eval_report import (
    CostBaseline,
    LiveBaseline,
    LiveCase,
    LiveSummary,
)

DATA: Final = "eval_data"
SCENARIOS: Final = "scenarios.json"
INJECTIONS: Final = "injections.json"
COST_BASELINE: Final = "cost_baseline.json"
LIVE_BASELINE: Final = "live_baseline.json"
SEPARATOR: Final = " | "


def data_text(name: str) -> str:
    """One data file of the package."""
    return files(__package__).joinpath(DATA, name).read_text("utf-8")


def load_scenarios() -> tuple[EvalScenario, ...]:
    """The shipped scenarios."""
    return EvalScenarios.model_validate_json(data_text(SCENARIOS)).scenarios


def load_corpus() -> InjectionCorpus:
    """The shipped injection corpus."""
    return InjectionCorpus.model_validate_json(data_text(INJECTIONS))


def load_cost_baseline() -> CostBaseline:
    """The scripted scenarios' recorded cost."""
    return CostBaseline.model_validate_json(data_text(COST_BASELINE))


def load_live_baseline() -> LiveBaseline | None:
    """The live suites' recorded scores; None until a first run records them."""
    path = files(__package__).joinpath(DATA, LIVE_BASELINE)
    if not path.is_file():
        return None
    return LiveBaseline.model_validate_json(path.read_text("utf-8"))


def write_text(directory: Path, name: str, text: str) -> Path:
    """A file of the report's directory, made when missing."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, "utf-8")
    return path


def live_report_json(summary: LiveSummary, cases: list[LiveCase], problems: list[str]) -> str:
    """Every case and the summary, for tools."""
    report = {
        "summary": json.loads(json.dumps(asdict(summary), default=str)),
        "regressions": problems,
        "cases": [json.loads(json.dumps(asdict(case), default=str)) for case in cases],
    }
    return json.dumps(report, ensure_ascii=False, indent=2)


def live_report_markdown(
    summary: LiveSummary, cases: list[LiveCase], problems: list[str], model: str
) -> str:
    """The run for the change's record: scores, languages, regressions and failed cases."""
    lines = [
        "# Leo live evaluation",
        "",
        f"Model: `{model}`. Cases: {summary.cases}. Model calls: {summary.cost.model_calls}, "
        f"input tokens (estimated): {summary.cost.input_tokens}, output tokens: "
        f"{summary.cost.output_tokens}, reported cost: ${summary.cost_usd:.4f}.",
        "",
        "| Suite | Score |",
        "| --- | --- |",
        *(f"| {suite} | {score:.1%} |" for suite, score in summary.scores.items()),
        "",
        "| Language | Tool choice |",
        "| --- | --- |",
        *(f"| {language} | {score:.1%} |" for language, score in summary.languages.items()),
        "",
        "## Regressions against the baseline",
        "",
        *([f"- {problem}" for problem in problems] or ["None."]),
        "",
        "## Failed cases",
        "",
    ]
    failed = [case for case in cases if case_failed(case)]
    for case in failed:
        reasons = [*case.tool_problems, *case.answer_problems]
        if case.judge is not None and not case.judge.passed:
            reasons.append(f"judge: {case.judge.reason}")
        lines.append(f"- `{case.scenario}` ({case.language}): {SEPARATOR.join(reasons)}")
    if not failed:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def scripted_report_markdown(findings: dict[str, list[str]], costs: dict[str, CostLine]) -> str:
    """The deterministic suites' run: each case's findings and each scenario's cost."""
    lines = [
        "# Leo scripted evaluation",
        "",
        "| Scenario | Model calls | Input tokens | Output tokens |",
        "| --- | --- | --- | --- |",
        *(
            f"| {name} | {cost.model_calls} | {cost.input_tokens} | {cost.output_tokens} |"
            for name, cost in costs.items()
        ),
        "",
        "## Findings",
        "",
    ]
    failed = {case: found for case, found in findings.items() if found}
    lines += [f"- `{case}`: {SEPARATOR.join(found)}" for case, found in failed.items()] or ["None."]
    return "\n".join(lines) + "\n"


def case_failed(case: LiveCase) -> bool:
    """Whether any suite failed the case."""
    judged_badly = case.judge is not None and not case.judge.passed
    return bool(case.tool_problems or case.answer_problems or judged_badly)
