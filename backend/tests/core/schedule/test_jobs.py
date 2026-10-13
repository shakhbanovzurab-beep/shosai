"""A periodic job or a due-row source is a tick task of the homes it names."""

from datetime import timedelta
from typing import cast

import pytest

from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import DueRowSource, PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload, TaskPayload
from shosai.core.tasks.queues import TaskQueue
from tests.core.schedule.jobs_bench import tick


class OtherPayload(TaskPayload):
    """A payload without a home."""


def test_a_job_is_named_by_its_task_and_runs_in_every_home_by_default() -> None:
    job = PeriodicJob(tick("probe.hourly_digest"), timedelta(hours=1))

    assert (job.name, job.homes) == ("probe.hourly_digest", (Home.RU, Home.EU))


def test_a_job_must_be_a_home_tick_of_at_least_a_minute() -> None:
    work = TaskDeclaration(
        name="probe.mail", queue=TaskQueue.DEFAULT, payload=HomeTaskPayload,
        deadline=timedelta(minutes=1), retry=NO_RETRY,
    )  # fmt: skip
    homeless = TaskDeclaration(
        name="probe.tick", queue=TaskQueue.DEFAULT, payload=OtherPayload,
        deadline=timedelta(minutes=1), retry=NO_RETRY, kind=TaskKind.TICK,
    )  # fmt: skip

    # Чужой тип нагрузки — сам предмет проверки: время выполнения ловит то, что cast скрыл.
    for task in (work, cast("TaskDeclaration[HomeTaskPayload]", homeless)):
        with pytest.raises(ValueError, match="такт с HomeTaskPayload"):
            PeriodicJob(task, timedelta(hours=1))
    with pytest.raises(ValueError, match="не короче минуты"):
        PeriodicJob(tick("probe.often"), timedelta(seconds=30))
    with pytest.raises(ValueError, match="без повторов"):
        PeriodicJob(tick("probe.twice"), timedelta(hours=1), homes=(Home.RU, Home.RU))


def test_a_due_row_source_is_a_tick_of_at_least_a_second() -> None:
    source = DueRowSource(tick("probe.sweep_due"), timedelta(seconds=5), homes=(Home.EU,))

    assert source.name == "probe.sweep_due"
    with pytest.raises(ValueError, match="не короче секунды"):
        DueRowSource(tick("probe.sweep_due"), timedelta(milliseconds=500))
