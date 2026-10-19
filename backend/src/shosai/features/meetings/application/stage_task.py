"""The task of one stage of a run, on the `meeting` queue (§4.2, §4.3, §12).

A delivery runs one stage. A stage that failed in a way another attempt may cure raises
`StageRetryError` after its failure is committed, and the broker delivers it again after its
back-off (5 seconds doubling to 120, with jitter); a stage that keeps failing stops after
three attempts, counted in the run's row, whatever path delivers it. The deadline covers
the longest stage — a long recording's transcription — and a worker that dies mid-stage
leaves the stage to be taken over after the hold limit.
"""

from datetime import timedelta
from typing import Final
from uuid import UUID

from shosai.core.tasks.declaration import TRANSIENT_FAILURES, RetryPolicy, TaskDeclaration
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.meetings.domain.runs import Stage


class StageRetryError(Exception):
    """The stage's failure is committed; another delivery may succeed after the back-off."""


class StagePayload(HomeTaskPayload):
    """One stage of one run, in the scope of the run's meeting."""

    run_id: UUID
    stage: Stage


RUN_STAGE: Final = TaskDeclaration(
    name="meetings.run_stage",
    queue=TaskQueue.MEETING,
    payload=StagePayload,
    deadline=timedelta(minutes=15),
    retry=RetryPolicy(max_deliveries=5, retry_on=(StageRetryError, *TRANSIENT_FAILURES)),
)
