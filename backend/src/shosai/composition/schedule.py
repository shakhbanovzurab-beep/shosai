"""The periodic jobs of a process: core's own and every slice's, checked once at start.

Core's daily jobs — the purge of published events, the purge of expired effect keys and the
upkeep of monthly partitions — are periodic jobs like any slice's, so a deploy does not run
them again (F1 audit A8, F6 step 1). A job or a due-row source whose task this process did
not register stops the start: the walk would queue a task no worker can run.
"""

from typing import Final

from shosai.core.ai.pricing.sync import SYNC_PRICES_JOB
from shosai.core.db.partitions.system import MAINTAIN_EVERY, MAINTAIN_PARTITIONS
from shosai.core.email.system import PURGE_EMAIL_JOB
from shosai.core.events.system import PURGE_EVERY, PURGE_OUTBOX
from shosai.core.exchange_rates.fetch import FETCH_RATES_JOB
from shosai.core.features import FeatureParts
from shosai.core.idempotency.system import PURGE_EFFECT_KEYS, PURGE_KEYS_EVERY
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.schedule.walker import check_job_names
from shosai.core.tasks.system import TaskSystem

CORE_JOBS: Final = (
    PeriodicJob(PURGE_OUTBOX, PURGE_EVERY),
    PeriodicJob(PURGE_EFFECT_KEYS, PURGE_KEYS_EVERY),
    PeriodicJob(MAINTAIN_PARTITIONS, MAINTAIN_EVERY),
    FETCH_RATES_JOB,
    SYNC_PRICES_JOB,
    PURGE_EMAIL_JOB,
)


def scheduled_jobs(parts: FeatureParts, tasks: TaskSystem) -> tuple[PeriodicJob, ...]:
    """Core's and the slices' periodic jobs, each named once and each task registered."""
    jobs = (*CORE_JOBS, *parts.periodic_jobs)
    check_job_names(jobs)
    sources = [source.name for source in parts.due_sources]
    duplicates = sorted({name for name in sources if sources.count(name) > 1})
    if duplicates:
        message = f"источники строк к сроку объявлены дважды: {', '.join(duplicates)}"
        raise ValueError(message)
    unregistered = sorted(
        {job.task.name for job in jobs if not tasks.declares(job.task)}
        | {source.name for source in parts.due_sources if not tasks.declares(source.sweep)}
    )
    if unregistered:
        message = f"задачи по расписанию не зарегистрированы: {', '.join(unregistered)}"
        raise ValueError(message)
    return jobs
