"""The `whisperer` command line: one subcommand per role, a queue for a worker."""

import pytest

from whisperer.core.tasks.queues import TaskQueue
from whisperer.entrypoints.cli import build_parser, command

USAGE_ERROR = 2


@pytest.mark.parametrize(
    ("argv", "role"),
    [
        (["api"], "api"),
        (["ws"], "ws"),
        (["workers", "--queue", "meeting"], "workers"),
        (["scheduler"], "scheduler"),
        (["migrate", "current"], "migrate"),
    ],
)
async def test_each_role_is_a_subcommand(argv: list[str], role: str) -> None:
    arguments = build_parser().parse_args(argv)

    coroutine = command(arguments, {})
    coroutine.close()

    assert arguments.role == role


def test_a_worker_takes_one_known_queue() -> None:
    parser = build_parser()

    assert TaskQueue(parser.parse_args(["workers", "--queue", "bulk"]).queue) is TaskQueue.BULK
    for argv in (["workers"], ["workers", "--queue", "slow"], ["migrate", "downgrade"], []):
        with pytest.raises(SystemExit) as raised:
            parser.parse_args(argv)
        assert raised.value.code == USAGE_ERROR
