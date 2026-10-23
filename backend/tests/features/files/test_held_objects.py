"""Objects files holds for other slices: counted once, kept until their last holder, previewed
(files step 8c; ADR 0064)."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta
from io import BytesIO
from typing import cast

import httpx
import pytest
import pytest_asyncio
from PIL import Image
from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.config.roles import ProcessRole
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.files.application.held_objects import HeldObjectsService
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.application.preview_task import PreviewPayload
from shosai.features.files.application.previews import Previews
from shosai.features.files.application.quota_reconciliation import QuotaReconciliation
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.contracts.held_objects import HeldObject
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.infrastructure.held_records import HeldObjectRecord
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import Viewer
from tests.features.files.file_bench import EDGE, FileBench
from tests.features.files.upload_bench import GuardedTransactions, person
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

HOME = Home.EU
ATTACHMENT = UploadPurpose.TASK_ATTACHMENT


@dataclass
class Sent:
    """The preview tasks the test's queue received."""

    payloads: list[PreviewPayload] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[PreviewPayload], payload: PreviewPayload) -> str:
        """Record the task."""
        del task
        self.payloads.append(payload)
        return str(uuid.uuid4())


@dataclass
class HeldBench:
    """Held objects and previews over the File Manager's bench."""

    files: FileBench
    held: HeldObjectsService
    previews: Previews
    sent: Sent
    # Транзакции воркеров: обходы по всем тенантам разрешены только им.
    workers: HomeTransactions

    async def uploaded(self, who: Principal, body: bytes, content_type: str) -> uuid.UUID:
        """A ready `task_attachment` upload of `body`."""
        request = UploadRequest(ATTACHMENT, "вложение.bin", content_type, len(body))
        view = await self.files.uploads.service.create(who, request)
        [link] = view.links
        async with httpx.AsyncClient() as client:
            answer = await client.put(
                link.request.url, content=body, headers=dict(link.request.headers)
            )
        assert answer.status_code == 200, answer.text
        await self.files.uploads.service.complete(who, view.id)
        return view.id

    async def hold(self, who: Principal, upload_id: uuid.UUID) -> HeldObject:
        """The upload held in the person's transaction."""
        scope = TenancyScope(who.home, who.user_id)
        async with self.files.uploads.transactions.begin(scope) as session:
            return await self.held.from_upload(session, upload_id, ATTACHMENT)

    async def release(self, who: Principal, held_id: uuid.UUID) -> tuple[str, ...]:
        """Release the held object, then discard what it left unnamed."""
        scope = TenancyScope(who.home, who.user_id)
        async with self.files.uploads.transactions.begin(scope) as session:
            keys = await self.held.release(session, [held_id])
        await self.held.discard(who.home, keys)
        return keys

    async def record(self, who: Principal, held_id: uuid.UUID) -> HeldObjectRecord | None:
        """The held object's row."""
        scope = TenancyScope(who.home, who.user_id)
        async with self.files.uploads.transactions.begin(scope, read_only=True) as session:
            return await session.scalar(
                select(HeldObjectRecord).where(HeldObjectRecord.id == held_id)
            )

    async def exists(self, key: str) -> bool:
        """Whether the bucket still has the object."""
        return await self.files.uploads.objects[HOME].head(key) is not None


@pytest_asyncio.fixture
async def held_bench(file_bench: FileBench, run_slot: RunSlot) -> AsyncIterator[HeldBench]:
    """Held objects over the guarded storage: no storage call inside a transaction; the
    previews, the purge and the reconciliation run as the workers do."""
    uploads = file_bench.uploads
    sent = Sent()
    storage = uploads.storage.objects
    held = HeldObjectsService(
        uploads.transactions, file_bench.ports, (storage, uploads.deleter, EDGE),
        (sent, uploads.claims),
    )  # fmt: skip
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        guarded = cast("HomeTransactions", GuardedTransactions(workers.transactions, uploads.guard))
        previews = Previews(guarded, (storage, uploads.deleter), sent, uploads.clock)
        yield HeldBench(file_bench, held, previews, sent, guarded)


def png(width: int = 1600, height: int = 900) -> bytes:
    """A PNG of the size."""
    out = BytesIO()
    Image.new("RGB", (width, height), (40, 120, 200)).save(out, format="PNG")
    return out.getvalue()


async def test_an_upload_is_held_once_in_its_owners_prefix_and_counted_once(
    held_bench: HeldBench,
) -> None:
    who = person(HOME, uuid.uuid4())
    upload_id = await held_bench.uploaded(who, b"contract", "application/pdf")

    first = await held_bench.hold(who, upload_id)
    again = await held_bench.hold(who, upload_id)
    record = await held_bench.record(who, first.id)

    assert again == first
    assert (first.image, first.size_bytes) == (False, 8)
    assert record is not None
    assert record.object_key == f"u/{who.user_id}/h/{upload_id}"
    assert await held_bench.files.used(who) == 8


async def test_a_workspace_is_not_included_until_its_storage_opens(held_bench: HeldBench) -> None:
    who = person(HOME, uuid.uuid4())
    service = held_bench.files.uploads.service
    workspace = uuid.uuid4()

    with pytest.raises(AppError) as held:
        await service.create(
            who, UploadRequest(ATTACHMENT, "a.pdf", "application/pdf", 9, workspace)
        )
    with pytest.raises(AppError) as managed:
        await service.create(
            who, UploadRequest(UploadPurpose.FILE_MANAGER, "a.pdf", "application/pdf", 9, workspace)
        )
    upload_id = await held_bench.uploaded(who, b"workspace", "application/pdf")
    scope = TenancyScope(HOME, who.user_id, workspace)
    with pytest.raises(AppError) as in_workspace:
        async with held_bench.files.uploads.transactions.begin(scope) as session:
            await held_bench.held.from_upload(session, upload_id, ATTACHMENT)

    assert (held.value.code, held.value.status) == ("storage_not_included", 403)
    assert managed.value.code == "validation_error"
    assert in_workspace.value.code == "storage_not_included"


async def test_a_copied_files_object_outlives_the_files_purge_until_its_last_holder_goes(
    held_bench: HeldBench,
) -> None:
    files = held_bench.files
    who = person(HOME, uuid.uuid4())
    source = await files.file(who, "Отчёт.pdf", b"quarterly")
    limit = await held_bench.held.limit(HOME, who.user_id)
    async with files.uploads.transactions.begin(TenancyScope(HOME, who.user_id)) as session:
        copy = await held_bench.held.from_file(
            session, Viewer(who.user_id), source.id, (ATTACHMENT, limit)
        )
    record = await held_bench.record(who, copy.id)
    assert record is not None
    key = record.object_key

    charged = await files.used(who)
    await files.manager.delete(who, source.id)
    files.uploads.clock.now += timedelta(days=8)
    await HiddenFiles(held_bench.workers, files.uploads.deleter, files.uploads.clock).purge(HOME)
    kept = await held_bench.exists(key)
    released = await held_bench.release(who, copy.id)

    assert (copy.filename, charged) == ("Отчёт.pdf", 18)
    assert kept
    assert released == (key,)
    assert not await held_bench.exists(key)
    assert await files.used(who) == 0


async def test_a_copy_past_the_plan_is_refused_and_an_unreadable_file_is_not_found(
    held_bench: HeldBench,
) -> None:
    files = held_bench.files
    who, stranger = person(HOME, uuid.uuid4()), person(HOME, uuid.uuid4())
    source = await files.file(who, "a.pdf", b"bytes")
    files.uploads.plan.file_manager_gb = 0
    limit = await held_bench.held.limit(HOME, who.user_id)

    async def copy(as_whom: Principal) -> None:
        scope = TenancyScope(HOME, as_whom.user_id)
        async with files.uploads.transactions.begin(scope) as session:
            await held_bench.held.from_file(
                session, Viewer(as_whom.user_id), source.id, (ATTACHMENT, limit)
            )

    with pytest.raises(AppError) as refused:
        await copy(who)
    with pytest.raises(AppError) as unreadable:
        await copy(stranger)

    assert refused.value.code == "storage_not_included"
    assert unreadable.value.code == "file_not_found"


async def test_an_image_gets_its_preview_and_a_broken_one_leaves_none(
    held_bench: HeldBench,
) -> None:
    who = person(HOME, uuid.uuid4())
    image = await held_bench.hold(who, await held_bench.uploaded(who, png(), "image/png"))
    broken = await held_bench.hold(who, await held_bench.uploaded(who, b"not a png", "image/png"))

    await held_bench.held.prepare(HOME, [image.id, broken.id])
    for payload in held_bench.sent.payloads:
        await held_bench.previews.make(payload.home, payload.held_id)
    links = await held_bench.held.previews(TenancyScope(HOME, who.user_id), [image.id, broken.id])
    made = await held_bench.record(who, image.id)
    failed = await held_bench.record(who, broken.id)
    assert made is not None
    assert made.preview_key is not None
    async with held_bench.files.uploads.objects[HOME].open(made.preview_key) as stream:
        preview = Image.open(BytesIO(b"".join([chunk async for chunk in stream.chunks(65536)])))

    assert (image.image, broken.image) == (True, True)
    assert set(links) == {image.id}
    assert links[image.id].startswith(EDGE)
    assert (preview.format, preview.size) == ("WEBP", (640, 360))
    assert failed is not None
    assert (failed.preview_state, failed.preview_key) == ("failed", None)


async def test_a_preview_left_waiting_is_queued_again_and_a_released_image_takes_its_preview(
    held_bench: HeldBench,
) -> None:
    who = person(HOME, uuid.uuid4())
    image = await held_bench.hold(who, await held_bench.uploaded(who, png(), "image/png"))

    held_bench.files.uploads.clock.now += timedelta(minutes=11)
    queued = await held_bench.previews.retry(HOME)
    await held_bench.previews.make(HOME, image.id)
    record = await held_bench.record(who, image.id)
    assert record is not None
    assert record.preview_key is not None
    released = await held_bench.release(who, image.id)

    assert queued >= 1
    assert image.id in {payload.held_id for payload in held_bench.sent.payloads}
    assert set(released) == {record.object_key, record.preview_key}
    assert not await held_bench.exists(record.preview_key)


async def test_the_reconciliation_counts_held_objects_with_files(held_bench: HeldBench) -> None:
    files = held_bench.files
    who = person(HOME, uuid.uuid4())
    await files.file(who, "a.pdf", b"file")
    await held_bench.hold(who, await held_bench.uploaded(who, b"attachment", "application/pdf"))
    reconciliation = QuotaReconciliation(
        held_bench.workers,
        (files.uploads.storage.objects, QuotaMetrics(CollectorRegistry())),
        files.uploads.clock,
    )

    drifted, _ = await reconciliation.run(HOME)

    assert await files.used(who) == 14
    assert drifted == 0
