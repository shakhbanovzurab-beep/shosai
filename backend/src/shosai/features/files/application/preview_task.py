"""The task that makes a held image's preview, on the bulk queue (ADR 0064 point 5).

A holder queues it after its commit through `HeldObjects.prepare`; the upload sweep queues
again an image whose preview is still to make, so a lost delivery only delays it. A failure
the next delivery may cure — the bucket or the home out of reach — is retried.
"""

from datetime import timedelta
from typing import Final, Protocol
from uuid import UUID

from shosai.core.tasks.declaration import RETRY_TRANSIENT, TaskDeclaration
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue


class PreviewPayload(HomeTaskPayload):
    """The held object whose preview to make."""

    held_id: UUID


MAKE_PREVIEW: Final = TaskDeclaration(
    name="files.make_preview",
    queue=TaskQueue.BULK,
    payload=PreviewPayload,
    deadline=timedelta(minutes=2),
    retry=RETRY_TRANSIENT,
)


class PreviewSender(Protocol):
    """Queues a preview's task: the process's `TaskSender`."""

    async def send(self, task: TaskDeclaration[PreviewPayload], payload: PreviewPayload) -> str:
        """Queue the task; `TaskQueueUnavailableError` when the queue does not answer."""
        ...
