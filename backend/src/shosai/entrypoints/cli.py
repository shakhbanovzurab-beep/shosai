"""`shosai`: the one console command of the backend image (target architecture §5).

    shosai api                     public API on HTTP_PORT
    shosai ws                      WS gateway on HTTP_PORT
    shosai workers --queue QUEUE   worker of one task queue
    shosai scheduler               scheduled loops
    shosai migrate upgrade         apply migrations to both homes, RU first
    shosai migrate current         log each home's revision

Every long-running role also serves `/livez`, `/readyz` and `/metrics` on OPS_PORT. The
settings come from the environment only (`.env.example`, section 2). One process runs
one role on one uvloop event loop.
"""

import argparse
import os
from collections.abc import Coroutine, Mapping, Sequence
from typing import Any

import uvloop

from shosai.composition.migrate import MigrateAction, run_migrate
from shosai.composition.process import run_process
from shosai.composition.roles import api_role, scheduler_role, workers_role, ws_role
from shosai.core.config.roles import ProcessRole
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
    return parser


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
        case ProcessRole.MIGRATE:
            return run_migrate(environ, MigrateAction(arguments.action))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the role named on the command line; the console script exits with the result."""
    arguments = build_parser().parse_args(argv)
    # Окружение читается один раз, здесь; дальше настройки передаются явно.
    return uvloop.run(command(arguments, dict(os.environ)))
