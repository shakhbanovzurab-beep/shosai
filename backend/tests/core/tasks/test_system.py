"""Every process registers every task once, each on the broker of its queue."""

import sys

import pytest
from redis.asyncio import Redis

from tests.core.tasks.workbench import Runs, declare, workbench
from whisperer.core.tasks import handlers
from whisperer.core.tasks.queues import TaskQueue

RUNS = Runs()


def test_every_queue_has_a_broker_with_the_tasks_of_that_queue(valkey: Redis) -> None:
    critical, bulk = declare("probe.mail", queue=TaskQueue.CRITICAL), declare("probe.export")
    bench = workbench(valkey, [RUNS.handler(critical), RUNS.handler(bulk)])

    assert set(bench.system.brokers) == set(TaskQueue)
    assert bench.broker(TaskQueue.CRITICAL).declaration(critical.name) is critical
    assert bench.broker(TaskQueue.CRITICAL).find_task(critical.name) is not None
    assert bench.broker(TaskQueue.DEFAULT).declaration(bulk.name) is bulk
    assert bench.broker(TaskQueue.DEFAULT).declaration(critical.name) is None


def test_a_task_name_is_declared_once_in_the_backend(valkey: Redis) -> None:
    same_queue = [RUNS.handler(declare("probe.twice")), RUNS.handler(declare("probe.twice"))]
    other_queue = [
        RUNS.handler(declare("probe.twice")),
        RUNS.handler(declare("probe.twice", queue=TaskQueue.BULK)),
    ]

    for handlers_list in (same_queue, other_queue):
        with pytest.raises(ValueError, match="дважды"):
            workbench(valkey, handlers_list)


def test_a_broker_takes_only_the_tasks_of_its_queue(valkey: Redis) -> None:
    bench = workbench(valkey, [])

    with pytest.raises(ValueError, match="объявлена для очереди"):
        bench.broker(TaskQueue.BULK).register(RUNS.handler(declare("probe.misplaced")))


def test_registration_leaves_the_handler_module_untouched(valkey: Redis) -> None:
    task = declare("probe.clean")
    bench = workbench(valkey, [RUNS.handler(task)])

    registered = bench.broker().find_task(task.name)
    assert registered is not None
    assert registered.original_func.__name__ == "run_task"
    assert not [name for name in vars(sys.modules[handlers.__name__]) if "taskiq" in name]
