"""Files' held objects for the task bench: real uploads, objects and previews over the slot.

A task's attachment is held by files' own `HeldObjectsService` over the slot's buckets; the
preview queue is the test's list, and the previews run as the workers do. A File Manager
file is written straight to its table and bucket, as files' steps leave one.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.files.application.held_objects import HeldObjectsService
from shosai.features.files.application.preview_task import PreviewPayload
from shosai.features.files.application.previews import Previews
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.domain.keys import PersonOwner, file_key
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from tests.features.files.upload_bench import UploadBench, person
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

HOME = Home.EU
EDGE = "https://shosai.tech/dl"


@dataclass
class Queued:
    """The preview tasks the test's queue received."""

    payloads: list[PreviewPayload] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[PreviewPayload], payload: PreviewPayload) -> str:
        """Record the task."""
        del task
        self.payloads.append(payload)
        return str(uuid.uuid4())


@dataclass
class Holding:
    """Uploads, files and held objects of the bench."""

    uploads: UploadBench
    held: HeldObjectsService
    previews: Previews
    queued: Queued

    async def uploaded(self, who: uuid.UUID, body: bytes, content_type: str) -> uuid.UUID:
        """A ready `task_attachment` upload of `body` by the person."""
        principal = person(HOME, who)
        request = UploadRequest(UploadPurpose.TASK_ATTACHMENT, "Схема.png", content_type, len(body))
        view = await self.uploads.service.create(principal, request)
        [link] = view.links
        async with httpx.AsyncClient() as client:
            answer = await client.put(
                link.request.url, content=body, headers=dict(link.request.headers)
            )
        assert answer.status_code == 200, answer.text
        await self.uploads.service.complete(principal, view.id)
        return view.id

    async def file(self, who: uuid.UUID, name: str, body: bytes) -> tuple[uuid.UUID, str]:
        """A File Manager file of the person, counted in their storage: its id and key."""
        file_id = uuid.uuid4()
        key = file_key(PersonOwner(who), file_id)
        await self.uploads.objects[HOME].put(key, body, content_type="application/pdf")
        async with self.uploads.transactions.begin(TenancyScope(HOME, who)) as session:
            session.add(StorageUsageRecord(user_id=who, used_bytes=len(body)))
            session.add(
                StorageFileRecord(
                    id=file_id, user_id=who, name=name, content_type="application/pdf",
                    size_bytes=len(body), object_key=key,
                )
            )  # fmt: skip
        return file_id, key

    async def used(self, who: uuid.UUID) -> int:
        """The person's used bytes."""
        async with self.uploads.transactions.begin(
            TenancyScope(HOME, who), read_only=True
        ) as session:
            row = await session.get(StorageUsageRecord, who)
        return 0 if row is None else row.used_bytes

    async def exists(self, key: str) -> bool:
        """Whether the bucket still has the object."""
        return await self.uploads.objects[HOME].head(key) is not None

    async def make_previews(self) -> None:
        """Run every queued preview, as the workers would."""
        for payload in self.queued.payloads:
            await self.previews.make(payload.home, payload.held_id)


@asynccontextmanager
async def holding(
    uploads: UploadBench, ports: PortDirectory, run_slot: RunSlot
) -> AsyncIterator[Holding]:
    """Held objects over the bench's uploads and ports; previews in workers' transactions."""
    queued = Queued()
    held = HeldObjectsService(
        uploads.transactions, ports, (uploads.objects, uploads.deleter, EDGE),
        (queued, uploads.claims),
    )  # fmt: skip
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        previews = Previews(workers.transactions, (uploads.objects, uploads.deleter), queued)
        yield Holding(uploads, held, previews, queued)
