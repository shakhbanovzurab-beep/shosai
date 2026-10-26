"""`shosai agent eval cases`: Leo's donated evaluation cases on the host (ADR 0068 AG-D13, AG-D8;
agent step 11c).

    shosai agent eval cases list          counts by home, rating, language and model — no text
    shosai agent eval cases show ID       one case as JSON on standard output
    shosai agent eval cases replay [--rating R] [--language CODE] [--limit N] [--judge-model M]

Unlike the suites of made-up people, cases live in the people's homes, so the command runs where
they live, in any environment. Every case shown or replayed leaves a row of the admin's audit
log. The replay asks today's model each case again and has a judge compare the answers: "Useful"
cases are the guard set a change must not break — one that got worse fails the run — and "Not
useful" ones the set it should improve. Its report keeps scores only: the case's id, rating,
language and verdict, never a word of the conversation.
"""

import asyncio
import json
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TextIO
from uuid import UUID

import structlog

from shosai.composition.features import FEATURES
from shosai.composition.platform import Platform, open_platform
from shosai.composition.startup import load_process_settings
from shosai.composition.telemetry import open_telemetry
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.roles import ProcessRole
from shosai.features.agent.application.case_reads import CaseReads
from shosai.features.agent.application.case_replay import CaseReplay, CaseScore
from shosai.features.agent.domain.feedback import Rating
from shosai.features.agent.infrastructure.eval_files import write_text
from shosai.features.agent.settings import AgentSettings

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
# Повторов разом: каждый — два вызова модели.
AT_ONCE: Final = 4
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentCasesCommand:
    """What the owner asked for."""

    action: Literal["list", "show", "replay"]
    case_id: UUID | None
    rating: Rating | None
    language: str | None
    limit: int
    judge_model: str | None
    report: Path


async def run_agent_cases(
    environ: Mapping[str, str], command: AgentCasesCommand, out: TextIO = sys.stdout
) -> int:
    """List, show or replay the cases; return the exit code."""
    role = ProcessRole.AGENT
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    async with (
        open_telemetry(settings, role) as telemetry,
        open_platform(settings, role, telemetry, FEATURES) as platform,
    ):
        reads = CaseReads(platform.services.transactions, platform.services.ports)
        if command.action == "list":
            return await listed(reads, out)
        if command.action == "show":
            return await shown(reads, command.case_id, out)
        return await replayed(platform, reads, command)


async def listed(reads: CaseReads, out: TextIO) -> int:
    """The counts, one line each."""
    for count in await reads.counts():
        values = (count.home.value, count.rating.value, count.language, count.model, count.cases)
        out.write("\t".join(str(value) for value in values) + "\n")
    return EXIT_OK


async def shown(reads: CaseReads, case_id: UUID | None, out: TextIO) -> int:
    """One case as JSON, its read recorded."""
    ref = None if case_id is None else await reads.find(case_id)
    stored = None if ref is None else await reads.read(ref)
    if stored is None:
        log.error("Оценочного случая нет", case=str(case_id))
        return EXIT_FAILED
    out.write(json.dumps(stored.case, ensure_ascii=False, indent=2) + "\n")
    return EXIT_OK


async def replayed(platform: Platform, reads: CaseReads, command: AgentCasesCommand) -> int:
    """Every chosen case replayed and judged; the scores into the report."""
    standard = platform.services.settings.features.get(AgentSettings).standard_route()
    if standard is None:
        log.error("Повтор оценочных случаев без модели: не задан AGENT_STANDARD_MODEL")
        return EXIT_FAILED
    model = command.judge_model
    judging = ModelRoute(ModelRef(Provider.OPENROUTER, model)) if model else standard
    replay = CaseReplay(platform.services.ai, (standard, judging))
    refs = await reads.refs(command.rating, command.language, command.limit)
    gate = asyncio.Semaphore(AT_ONCE)

    async def one(index: int) -> CaseScore | None:
        async with gate:
            stored = await reads.read(refs[index])
            return None if stored is None else await replay.score(stored)

    scores = [s for s in await asyncio.gather(*(one(i) for i in range(len(refs)))) if s]
    report = report_of(scores)
    write_text(command.report, "cases.json", json.dumps(report, indent=2) + "\n")
    worse = report["guard_broken"]
    log.info(
        "Оценочные случаи повторены", report=str(command.report), cases=len(scores), worse=worse
    )
    return EXIT_FAILED if worse else EXIT_OK


def report_of(scores: list[CaseScore]) -> dict[str, object]:
    """The replay's report: counts and each case's verdict by id — no text."""
    results = Counter(
        (score.rating.value, "ungraded" if score.passed is None else str(score.passed).lower())
        for score in scores
    )
    return {
        "cases": len(scores),
        "results": {
            f"{rating}:{result}": count for (rating, result), count in sorted(results.items())
        },
        "guard_broken": results[(Rating.USEFUL.value, "false")],
        "scores": [
            {
                "case_id": str(score.case_id), "rating": score.rating.value,
                "language": score.language,
                "verdict": None if score.verdict is None else score.verdict.value,
                "passed": score.passed,
            }
            for score in scores
        ],
    }  # fmt: skip
