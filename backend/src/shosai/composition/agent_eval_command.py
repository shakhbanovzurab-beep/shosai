"""`shosai agent eval`: Leo's evaluation suites run by an engineer (AG-D8, Leo §11.4).

The live run asks the standard model every scenario in the platform's languages through
Leo's real turn, lets a judge grade the answers and compares the scores with the recorded
baseline; `--scripted` runs the deterministic suites CI runs, without a key or spend. Each
run writes its report to a directory of its own, and `--record REASON` adds the new baseline
for the change's record. The made-up people live in the development home only: the command
refuses any other environment, and erases each person after their run.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

import structlog

from shosai.composition.features import FEATURES
from shosai.composition.platform import Platform, open_platform
from shosai.composition.startup import load_process_settings
from shosai.composition.telemetry import open_telemetry
from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.agent_tools.spec import ToolSpec
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.roles import ProcessRole
from shosai.core.config.values import Environment
from shosai.core.db.engines import DATABASE_PROFILES
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.agent.application.eval_judge import Judge
from shosai.features.agent.application.eval_model import SCRIPTED_ROUTE
from shosai.features.agent.application.eval_runner import EvalRunner, EvalServices
from shosai.features.agent.application.eval_suites import (
    LiveSuite,
    safety_problems,
    scripted_languages,
    scripted_trajectory,
)
from shosai.features.agent.domain.eval_cases import EvalScenario
from shosai.features.agent.domain.eval_checks import CostLine, cost_regressions
from shosai.features.agent.domain.eval_report import (
    SUITE_DROP,
    CostBaseline,
    CostEntry,
    LiveBaseline,
    live_regressions,
    summarize,
)
from shosai.features.agent.infrastructure.eval_files import (
    COST_BASELINE,
    LIVE_BASELINE,
    live_report_json,
    live_report_markdown,
    load_corpus,
    load_cost_baseline,
    load_live_baseline,
    load_scenarios,
    scripted_report_markdown,
    write_text,
)
from shosai.features.agent.module import AGENT
from shosai.features.agent.settings import AgentSettings

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentEvalCommand:
    """What the engineer asked for."""

    scripted: bool
    scenarios: tuple[str, ...]
    languages: tuple[str, ...]
    judge_model: str | None
    judge: bool
    concurrency: int
    report: Path
    record: str | None


async def run_agent_eval(environ: Mapping[str, str], command: AgentEvalCommand) -> int:
    """Run the suites; return the exit code."""
    role = ProcessRole.AGENT
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    async with open_telemetry(settings, role) as telemetry:
        if settings.environment is not Environment.DEVELOPMENT:
            log.error("Оценка Leo идёт только в разработке", environment=settings.environment)
            return EXIT_FAILED
        async with open_platform(settings, role, telemetry, FEATURES) as platform:
            return await evaluate(platform, command)


def chosen(command: AgentEvalCommand) -> tuple[tuple[EvalScenario, ...], tuple[str, ...]] | None:
    """The scenarios and languages asked for, or None after naming an unknown one."""
    scenarios = load_scenarios()
    names = {scenario.id for scenario in scenarios}
    unknown = sorted(set(command.scenarios) - names) + sorted(
        set(command.languages) - set(SUPPORTED_LANGUAGES)
    )
    if unknown:
        log.error("Оценка Leo не знает сценариев или языков", unknown=unknown)
        return None
    picked = tuple(s for s in scenarios if not command.scenarios or s.id in command.scenarios)
    return picked, command.languages or SUPPORTED_LANGUAGES


async def evaluate(platform: Platform, command: AgentEvalCommand) -> int:
    """The asked suites over the open platform."""
    services = platform.services
    standard = services.settings.features.get(AgentSettings).standard_route()
    route = SCRIPTED_ROUTE if command.scripted else standard
    picked = chosen(command)
    if picked is None:
        return EXIT_FAILED
    if route is None:
        log.error("Живая оценка Leo без модели: не задан AGENT_STANDARD_MODEL")
        return EXIT_FAILED
    specs: tuple[ToolSpec[Any, Any], ...] = tuple(
        spec for feature in FEATURES if feature.name != AGENT.name for spec in feature.agent_tools
    )
    pool = DATABASE_PROFILES[ProcessRole.AGENT].pool_size
    runner = EvalRunner(
        EvalServices(
            transactions=services.transactions, valkey=services.valkey, effects=services.effects,
            limiter=services.rate_limiter, outbox=services.outbox,
            erasers=services.ports.all(ACCOUNT_DATA_HANDLERS), specs=specs,
            tool_calls_at_once=max(pool - 1, 1),
        ),
        route,
    )  # fmt: skip
    problems = runner.problems(picked[0])
    if problems:
        log.error("Сценарии оценки Leo не сходятся с инструментами", problems=problems)
        return EXIT_FAILED
    async with runner.serving():
        if command.scripted:
            return await scripted_run(runner, picked, command)
        judge = None
        if command.judge:
            model = command.judge_model
            judged_by = ModelRoute(ModelRef(Provider.OPENROUTER, model)) if model else route
            judge = Judge(services.ai, judged_by)
        suite = LiveSuite(runner, services.ai, judge, command.concurrency)
        return await live_run(suite, picked, command, route.primary.model)


async def scripted_run(
    runner: EvalRunner,
    picked: tuple[tuple[EvalScenario, ...], tuple[str, ...]],
    command: AgentEvalCommand,
) -> int:
    """The deterministic suites, as CI runs them."""
    scenarios, languages = picked
    findings: dict[str, list[str]] = {}
    costs: dict[str, CostLine] = {}
    for scenario in scenarios:
        outcome = await scripted_trajectory(runner, scenario)
        costs[scenario.id] = outcome.cost
        found = [*outcome.problems, *await scripted_languages(runner, scenario, languages)]
        findings[scenario.id] = found
    findings |= await safety_problems(runner, load_corpus())
    recorded = load_cost_baseline()
    lines = {name: line for name, line in recorded.lines().items() if name in costs}
    findings["cost"] = cost_regressions(costs, lines)
    write_text(command.report, "report.md", scripted_report_markdown(findings, costs))
    if command.record is not None:
        baseline = CostBaseline(
            reason=command.record, recorded_on=today(),
            scenarios={name: CostEntry.of(cost) for name, cost in costs.items()},
        )  # fmt: skip
        write_text(command.report, COST_BASELINE, baseline.model_dump_json(indent=2) + "\n")
        findings.pop("cost")
    failed = {case: found for case, found in findings.items() if found}
    log.info("Оценка Leo по сценарию закончена", report=str(command.report), failed=len(failed))
    return EXIT_FAILED if failed else EXIT_OK


async def live_run(
    suite: LiveSuite,
    picked: tuple[tuple[EvalScenario, ...], tuple[str, ...]],
    command: AgentEvalCommand,
    model: str,
) -> int:
    """The live suite, graded and compared with its baseline."""
    cases = await suite.run(*picked)
    summary = summarize(cases)
    baseline = load_live_baseline()
    problems = live_regressions(summary, baseline) if baseline is not None else []
    write_text(command.report, "report.json", live_report_json(summary, cases, problems))
    markdown = live_report_markdown(summary, cases, problems, model)
    write_text(command.report, "report.md", markdown)
    if command.record is not None:
        # Пол языка допускает один шумный случай: иначе любой промах модели — регрессия.
        per_language = summary.cases / max(len(summary.languages), 1)
        allowance = max(SUITE_DROP, 1 / per_language) if per_language else SUITE_DROP
        floor = max(0.0, min(summary.languages.values(), default=1.0) - allowance)
        recorded = LiveBaseline(
            reason=command.record, recorded_on=today(), model=model,
            scores=dict(summary.scores), language_floor=round(floor, 2),
        )  # fmt: skip
        write_text(command.report, LIVE_BASELINE, recorded.model_dump_json(indent=2) + "\n")
    log.info(
        "Живая оценка Leo закончена",
        report=str(command.report), cases=summary.cases, scores=dict(summary.scores),
        regressions=len(problems), cost_usd=str(summary.cost_usd), baseline=baseline is not None,
    )  # fmt: skip
    return EXIT_FAILED if problems else EXIT_OK


def today() -> date:
    """The day a baseline is recorded on, in UTC."""
    return datetime.now(UTC).date()


def default_report() -> Path:
    """A new directory for a run's report, named by its start."""
    return Path("agent-eval") / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
