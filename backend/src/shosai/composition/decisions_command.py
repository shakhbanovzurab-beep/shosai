"""`shosai decisions`: the Decision Layer's policies on the host (ADR 0069 DL-D6).

    shosai decisions dataset check|generate|draft-reference|label-reference …   the sets
    shosai decisions calibrate POINT@VERSION [--recorded] [--concurrency N]
    shosai decisions report POINT                     versions in force and revisions
    shosai decisions promote POINT@VERSION --revision N --to shadow|active [--note TEXT]
    shosai decisions retire POINT@VERSION [--note TEXT]

A calibration asks Jev every case live as the platform's own call — the cases hold no
person's data — and writes the point's recorded run beside the code; `--recorded` re-reads
the last run instead. Every revision is stored, passing or not; a promotion is refused,
with the reason, unless its revision passed every gate, and to active unless the version
spent its window in shadow. Output is numbers and codes only.
"""

import argparse
import json
import sys
from collections.abc import Coroutine, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal, TextIO

from shosai.composition.decisions_dataset_command import add_dataset, checked, made
from shosai.composition.features import FEATURES
from shosai.composition.platform import open_platform
from shosai.composition.startup import load_process_settings
from shosai.composition.telemetry import open_telemetry
from shosai.core.config.roles import ProcessRole
from shosai.features.decisions.application.calibration import Calibration
from shosai.features.decisions.application.promotion import Promotion
from shosai.features.decisions.domain.policies import policies_by_key
from shosai.features.decisions.infrastructure.policy_admin import PolicyAdmin
from shosai.features.decisions.settings import DecisionsSettings

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1

type Action = Literal[
    "check", "generate", "draft", "label", "calibrate", "report", "promote", "retire"
]

DATASET_ACTIONS: Final[Mapping[str, Action]] = {
    "check": "check",
    "generate": "generate",
    "draft-reference": "draft",
    "label-reference": "label",
}


@dataclass(frozen=True, slots=True)
class DecisionsCommand:
    """What the operator asked for."""

    action: Action
    target: str | None = None
    recorded: bool = False
    concurrency: int = 4
    revision: int | None = None
    state: str | None = None
    note: str | None = None
    language: str | None = None
    count: int = 0


def add_decisions(roles: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """`shosai decisions …`."""
    decisions = roles.add_parser(
        ProcessRole.DECISIONS.value, help="operator commands of the Decision Layer"
    )
    actions = decisions.add_subparsers(dest="action", required=True, metavar="ACTION")
    add_dataset(actions)
    calibrate = actions.add_parser("calibrate", help="fit and gate a version; store a revision")
    calibrate.add_argument("target", metavar="POINT@VERSION")
    calibrate.add_argument("--recorded", action="store_true", help="re-read the last live run")
    calibrate.add_argument(
        "--concurrency", type=int, default=4, choices=range(1, 17), metavar="1..16"
    )
    report = actions.add_parser("report", help="versions in force and revisions of a point")
    report.add_argument("target", metavar="POINT")
    promote = actions.add_parser("promote", help="a version with a revision to shadow or active")
    promote.add_argument("target", metavar="POINT@VERSION")
    promote.add_argument("--revision", type=int, required=True)
    promote.add_argument("--to", dest="state", choices=["shadow", "active"], required=True)
    promote.add_argument("--note", help="why, kept with the state")
    retire = actions.add_parser("retire", help="take a version out of force")
    retire.add_argument("target", metavar="POINT@VERSION")
    retire.add_argument("--note", help="why, kept with the state")


def decisions_command(arguments: argparse.Namespace) -> DecisionsCommand:
    """The command from the parsed arguments."""
    action: Action = arguments.action
    if arguments.action == "dataset":
        action = DATASET_ACTIONS[arguments.tool]
    return DecisionsCommand(
        action=action,
        target=getattr(arguments, "target", None),
        recorded=getattr(arguments, "recorded", False),
        concurrency=getattr(arguments, "concurrency", 4),
        revision=getattr(arguments, "revision", None),
        state=getattr(arguments, "state", None),
        note=getattr(arguments, "note", None),
        language=getattr(arguments, "language", None),
        count=getattr(arguments, "count", 0),
    )


def run_decisions(
    environ: Mapping[str, str], command: DecisionsCommand, out: TextIO = sys.stdout
) -> Coroutine[Any, Any, int]:
    """The coroutine of the command."""
    return _run(environ, command, out)


async def _run(environ: Mapping[str, str], command: DecisionsCommand, out: TextIO) -> int:
    if command.action == "check":
        return checked(out)
    role = ProcessRole.DECISIONS
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    async with (
        open_telemetry(settings, role) as telemetry,
        open_platform(settings, role, telemetry, FEATURES) as platform,
    ):
        services = platform.services
        admin = PolicyAdmin(services.transactions)
        if command.action == "report":
            return await reported(admin, command.target or "", out)
        if command.action in {"generate", "draft", "label"}:
            sizing = (command.language, command.count)
            return await made(services, command.action, command.target or "", sizing, out)
        if command.action == "calibrate":
            route = services.settings.features.get(DecisionsSettings).jev_route()
            return await calibrated(Calibration(admin, (services.ai, route)), command, out)
        return await changed(Promotion(admin, policies_by_key()), command, out)


async def calibrated(calibration: Calibration, command: DecisionsCommand, out: TextIO) -> int:
    """Calibrate one version and print its report."""
    policy = policies_by_key().get(command.target or "")
    if policy is None:
        out.write(f"version {command.target} is not in this image\n")
        return EXIT_FAILED
    result = await calibration.run(
        policy, live=not command.recorded, concurrency=command.concurrency
    )
    report = {"revision": result.revision, "passed": result.report.passed,
              "failures": list(result.report.failures), "unanswered": result.unanswered,
              "numbers": result.report.numbers}  # fmt: skip
    out.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return EXIT_OK if result.report.passed else EXIT_FAILED


async def reported(admin: PolicyAdmin, point: str, out: TextIO) -> int:
    """A point's versions in force and its revisions."""
    for state in await admin.states(point):
        since = f"{state.changed_at:%Y-%m-%d}"
        out.write(f"{point}@{state.version}: {state.state}, revision {state.revision}, {since}\n")
    for revision in await admin.revisions(point):
        verdict = "passed" if revision.passed else "failed"
        made = f"{revision.created_at:%Y-%m-%d}"
        out.write(f"{point}@{revision.version} revision {revision.revision}: {verdict}, {made}\n")
    return EXIT_OK


async def changed(promotion: Promotion, command: DecisionsCommand, out: TextIO) -> int:
    """Promote or retire a version."""
    target = command.target or ""
    if command.action == "promote":
        refusal = await promotion.promote(
            target, command.revision or 0, command.state or "", command.note
        )
    else:
        refusal = await promotion.retire(target, command.note)
    if refusal is not None:
        out.write(f"refused: {refusal.reason}\n")
        return EXIT_FAILED
    out.write(f"{target}: done\n")
    return EXIT_OK
