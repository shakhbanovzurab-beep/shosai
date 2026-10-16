"""The `shosai` command line: one subcommand per role, a queue for a worker."""

import pytest

from shosai.core.tasks.queues import TaskQueue
from shosai.entrypoints.cli import build_parser, command

USAGE_ERROR = 2


@pytest.mark.parametrize(
    ("argv", "role"),
    [
        (["api"], "api"),
        (["ws"], "ws"),
        (["workers", "--queue", "meeting"], "workers"),
        (["scheduler"], "scheduler"),
        (["migrate", "current"], "migrate"),
        (["observability", "debug"], "observability"),
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


def test_a_debug_switch_names_one_target_for_at_most_an_hour() -> None:
    parser = build_parser()
    user = "0190f0f0-0000-7000-8000-0000000000d7"

    arguments = parser.parse_args(["observability", "debug", "--user", user, "--minutes", "60"])
    assert (str(arguments.user), arguments.minutes, arguments.org) == (user, 60, None)
    for argv in (
        ["observability", "debug", "--user", user, "--minutes", "61"],
        ["observability", "debug", "--user", user, "--org", user],
        ["observability", "debug", "--user", "not-an-id"],
    ):
        with pytest.raises(SystemExit) as raised:
            parser.parse_args(argv)
        assert raised.value.code == USAGE_ERROR
