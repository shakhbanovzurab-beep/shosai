"""`shosai`: the one console command of the backend image (target architecture §5).

    shosai api                     public API on HTTP_PORT
    shosai ws                      WS gateway on HTTP_PORT
    shosai workers --queue QUEUE   worker of one task queue
    shosai scheduler               scheduled loops
    shosai migrate upgrade         apply migrations to both homes, RU first
    shosai migrate current         log each home's revision
    shosai ai kill-switch ACTION   engage, release or report the AI kill switch
    shosai ai rebuild-spend-counters   sum the AI spend counters again from the cost rows
    shosai email check --to ADDRESS    send a check mail of each kind through SMTP
    shosai identity admin-password-hash   print the bcrypt hash of the admin's password
    shosai observability debug --user ID --reason TEXT   DEBUG lines of one account for a while
    shosai files bucket-rules [--home ru|eu]   put ADR 0055's bucket lifecycle and CORS rules
    shosai agent eval [--scripted] [--scenario ID] [--language CODE] [--record REASON]
                                   Leo's evaluation suites, in development only

Every long-running role also serves `/livez`, `/readyz` and `/metrics` on OPS_PORT. The
settings come from the environment only (`.env.example`, section 2). One process runs
one role on one uvloop event loop.
"""

import argparse
import os
from collections.abc import Coroutine, Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

import uvloop

from shosai.composition.agent_eval_command import (
    AgentEvalCommand,
    default_report,
    run_agent_eval,
)
from shosai.composition.ai_command import KillSwitchAction, KillSwitchCommand, run_kill_switch
from shosai.composition.ai_rebuild import run_rebuild
from shosai.composition.email_command import MailCheckCommand, run_mail_check
from shosai.composition.files_command import run_bucket_rules
from shosai.composition.identity_command import run_admin_password_hash
from shosai.composition.migrate import MigrateAction, run_migrate
from shosai.composition.observability_command import DebugCommand, run_debug_switch
from shosai.composition.process import run_process
from shosai.composition.roles import api_role, scheduler_role, workers_role, ws_role
from shosai.core.config.roles import ProcessRole
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.core.kernel.homes import Home
from shosai.core.observability.debug_logs import DebugScope
from shosai.core.observability.debug_switches import LONGEST
from shosai.core.tasks.queues import TaskQueue

PROGRAM = "shosai"


def build_parser() -> argparse.ArgumentParser:
    """The command line: one subcommand per role."""
    parser = argparse.ArgumentParser(prog=PROGRAM, description="Shosai backend process.")
    roles = parser.add_subparsers(dest="role", required=True, metavar="ROLE")
    roles.add_parser(ProcessRole.API.value, help="serve the public API")
    roles.add_parser(ProcessRole.WS.value, help="serve the WebSocket gateway")
    workers = roles.add_parser(ProcessRole.WORKERS.value, help="run the tasks of one queue")
    workers.add_argument(
        "--queue", required=True, choices=[queue.value for queue in TaskQueue], help="task queue"
    )
    roles.add_parser(ProcessRole.SCHEDULER.value, help="run the scheduled loops")
    migrate = roles.add_parser(ProcessRole.MIGRATE.value, help="migrate both data homes")
    migrate.add_argument(
        "action", choices=[action.value for action in MigrateAction], help="what to do"
    )
    ai = roles.add_parser(ProcessRole.AI.value, help="operator commands of the AI port")
    tools = ai.add_subparsers(dest="tool", required=True, metavar="TOOL")
    switch = tools.add_parser("kill-switch", help="pause or resume expensive AI calls")
    switch.add_argument(
        "action", choices=[action.value for action in KillSwitchAction], help="what to do"
    )
    switch.add_argument("--reason", help="why, for engage; written to the log")
    switch.add_argument("--hours", type=float, default=24.0, help="how long engage holds")
    tools.add_parser("rebuild-spend-counters", help="sum the spend counters from the cost rows")
    email = roles.add_parser(ProcessRole.EMAIL.value, help="operator commands of the mail")
    mail_tools = email.add_subparsers(dest="tool", required=True, metavar="TOOL")
    check = mail_tools.add_parser("check", help="send a check mail of each kind")
    check.add_argument("--to", required=True, dest="recipient", help="where the check mail goes")
    check.add_argument(
        "--locale", default="en", choices=SUPPORTED_LANGUAGES, help="language of the mail"
    )
    identity = roles.add_parser(ProcessRole.IDENTITY.value, help="operator commands of accounts")
    account_tools = identity.add_subparsers(dest="tool", required=True, metavar="TOOL")
    account_tools.add_parser(
        "admin-password-hash", help="print the bcrypt hash of the admin's password"
    )
    add_observability(roles)
    add_agent(roles)
    files = roles.add_parser(ProcessRole.FILES.value, help="operator commands of the buckets")
    bucket_tools = files.add_subparsers(dest="tool", required=True, metavar="TOOL")
    rules = bucket_tools.add_parser(
        "bucket-rules", help="put the lifecycle and CORS rules on the homes' buckets"
    )
    rules.add_argument(
        "--home", choices=[home.value for home in Home], help="one home; both when omitted"
    )
    return parser


def add_observability(roles: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """`shosai observability debug`: DEBUG lines of one account or company for a while."""
    observability = roles.add_parser(
        ProcessRole.OBSERVABILITY.value, help="operator commands of logs and telemetry"
    )
    tools = observability.add_subparsers(dest="tool", required=True, metavar="TOOL")
    debug = tools.add_parser("debug", help="DEBUG lines of one account or company for a while")
    target = debug.add_mutually_exclusive_group()
    target.add_argument("--user", type=UUID, help="the account's id")
    target.add_argument("--org", type=UUID, help="the company's id")
    longest = int(LONGEST.total_seconds() // 60)
    debug.add_argument(
        "--minutes", type=int, default=15, choices=range(1, longest + 1), metavar=f"1..{longest}",
        help="how long the switch holds",
    )  # fmt: skip
    debug.add_argument("--reason", help="why, for switching on; written to the log")
    debug.add_argument("--off", action="store_true", help="end the switch now")


def add_agent(roles: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """`shosai agent eval`: Leo's evaluation suites (AG-D8)."""
    agent = roles.add_parser(ProcessRole.AGENT.value, help="engineer commands of Leo")
    tools = agent.add_subparsers(dest="tool", required=True, metavar="TOOL")
    evaluation = tools.add_parser("eval", help="run Leo's evaluation suites, in development only")
    evaluation.add_argument(
        "--scripted", action="store_true", help="the deterministic suites CI runs, without a key"
    )
    evaluation.add_argument(
        "--scenario", action="append", default=[], help="one scenario by id; every one if omitted"
    )
    evaluation.add_argument(
        "--language", action="append", default=[], choices=SUPPORTED_LANGUAGES,
        help="one language; all 16 if omitted",
    )  # fmt: skip
    evaluation.add_argument(
        "--judge-model", help="the judge's model; the standard model if omitted"
    )
    evaluation.add_argument("--no-judge", action="store_true", help="leave the answers ungraded")
    evaluation.add_argument(
        "--concurrency", type=int, default=4, choices=range(1, 9), metavar="1..8",
        help="cases run at once",
    )  # fmt: skip
    evaluation.add_argument("--report", type=Path, help="the report's directory")
    evaluation.add_argument("--record", metavar="REASON", help="also write the new baseline")


def agent_eval_command(arguments: argparse.Namespace) -> AgentEvalCommand:
    """The evaluation command from the parsed arguments."""
    return AgentEvalCommand(
        scripted=arguments.scripted,
        scenarios=tuple(arguments.scenario),
        languages=tuple(arguments.language),
        judge_model=arguments.judge_model,
        judge=not arguments.no_judge,
        concurrency=arguments.concurrency,
        report=arguments.report or default_report(),
        record=arguments.record,
    )


def debug_command(arguments: argparse.Namespace) -> DebugCommand:
    """The debug switch command from the parsed arguments."""
    if arguments.user is not None:
        scope, target = DebugScope.USER, arguments.user
    elif arguments.org is not None:
        scope, target = DebugScope.ORG, arguments.org
    else:
        scope, target = None, None
    return DebugCommand(scope, target, arguments.minutes, arguments.reason, off=arguments.off)


def command(arguments: argparse.Namespace, environ: Mapping[str, str]) -> Coroutine[Any, Any, int]:
    """The coroutine that runs the chosen role and returns the exit code."""
    role = ProcessRole(arguments.role)
    match role:
        case ProcessRole.API:
            return run_process(role, environ, api_role)
        case ProcessRole.WS:
            return run_process(role, environ, ws_role)
        case ProcessRole.WORKERS:
            return run_process(role, environ, workers_role(TaskQueue(arguments.queue)))
        case ProcessRole.SCHEDULER:
            return run_process(role, environ, scheduler_role)
        case ProcessRole.OBSERVABILITY | ProcessRole.AGENT:
            return engineer_command(role, arguments, environ)
        case (
            ProcessRole.MIGRATE
            | ProcessRole.AI
            | ProcessRole.EMAIL
            | ProcessRole.IDENTITY
            | ProcessRole.FILES
        ):
            return one_shot(role, arguments, environ)


def engineer_command(
    role: ProcessRole, arguments: argparse.Namespace, environ: Mapping[str, str]
) -> Coroutine[Any, Any, int]:
    """The coroutine of a debug switch or of Leo's evaluation."""
    if role is ProcessRole.AGENT:
        return run_agent_eval(environ, agent_eval_command(arguments))
    return run_debug_switch(environ, debug_command(arguments))


def one_shot(
    role: ProcessRole, arguments: argparse.Namespace, environ: Mapping[str, str]
) -> Coroutine[Any, Any, int]:
    """The coroutine of a one-shot command: migrations, an AI, mail, account or bucket command."""
    if role is ProcessRole.MIGRATE:
        return run_migrate(environ, MigrateAction(arguments.action))
    if role is ProcessRole.EMAIL:
        return run_mail_check(environ, MailCheckCommand(arguments.recipient, arguments.locale))
    if role is ProcessRole.IDENTITY:
        return run_admin_password_hash()
    if role is ProcessRole.FILES:
        homes = list(Home) if arguments.home is None else [Home(arguments.home)]
        return run_bucket_rules(environ, homes)
    return ai_command(arguments, environ)


def ai_command(
    arguments: argparse.Namespace, environ: Mapping[str, str]
) -> Coroutine[Any, Any, int]:
    """The coroutine of an operator's AI command."""
    if arguments.tool == "rebuild-spend-counters":
        return run_rebuild(environ)
    command = KillSwitchCommand(
        KillSwitchAction(arguments.action), arguments.reason, arguments.hours
    )
    return run_kill_switch(environ, command)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the role named on the command line; the console script exits with the result."""
    arguments = build_parser().parse_args(argv)
    # Окружение читается один раз, здесь; дальше настройки передаются явно.
    return uvloop.run(command(arguments, dict(os.environ)))
