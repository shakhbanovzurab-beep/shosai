"""Uploads straight to the bucket: ready, rejected, swept, claimed (files step 3; §10)."""

import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import MultipartUpload
from shosai.features.files.application.upload_links import UploadView
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.contracts import UploadNotClaimableError
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.domain.uploads import UploadState
from shosai.features.files.infrastructure.upload_records import (
    ObjectDeletionRecord,
    StorageUsageRecord,
    UploadRecord,
)
from tests.features.files.upload_bench import GIB, UploadBench, person
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

PDF = "application/pdf"


async def started(
    bench: UploadBench, who: object, size: int, purpose: UploadPurpose = UploadPurpose.FILE_MANAGER
) -> UploadView:
    request = UploadRequest(purpose, "Report.pdf", PDF, size)
    return await bench.service.create(who, request)  # type: ignore[arg-type]


async def put_part(view: UploadView, body: bytes) -> None:
    [link] = view.links
    async with httpx.AsyncClient() as client:
        answer = await client.put(
            link.request.url, content=body, headers=dict(link.request.headers)
        )
    assert answer.status_code == 200, answer.text


async def usage(bench: UploadBench, home: Home, user_id: uuid.UUID) -> tuple[int, int]:
    async with bench.transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
        row = await session.get(StorageUsageRecord, user_id)
    return (0, 0) if row is None else (row.used_bytes, row.reserved_bytes)


async def test_a_completed_upload_is_ready_and_a_retried_part_leaves_one_object(
    upload_bench: UploadBench,
) -> None:
    who = person(Home.RU, uuid.uuid4())
    view = await started(upload_bench, who, 1024)
    # Клиент повторяет часть после обрыва: те же байты по той же ссылке.
    await put_part(view, b"b" * 1024)
    await put_part(view, b"b" * 1024)
    resumed = await upload_bench.service.status(who, view.id)

    done = await upload_bench.service.complete(who, view.id)
    again = await upload_bench.service.complete(who, view.id)

    assert (resumed.done_parts, resumed.links) == ((1,), ())
    assert done.state is again.state is UploadState.READY
    async with upload_bench.storage.objects[Home.RU].open(f"u/{who.user_id}/f/{view.id}") as stream:
        body = b"".join([chunk async for chunk in stream.chunks(4096)])
    assert body == b"b" * 1024
    assert await usage(upload_bench, Home.RU, who.user_id) == (0, 1024)


async def test_an_object_of_another_size_is_rejected_its_bytes_released_and_deleted(
    upload_bench: UploadBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    view = await started(upload_bench, who, 2048)
    key = f"u/{who.user_id}/f/{view.id}"
    async with upload_bench.transactions.begin(
        TenancyScope(Home.EU, who.user_id), read_only=True
    ) as session:
        record = await session.get(UploadRecord, view.id)
    assert record is not None
    await upload_bench.storage.uploads[Home.EU].upload_part(
        MultipartUpload(key, record.multipart_id), 1, b"x" * 1000
    )

    rejected = await upload_bench.service.complete(who, view.id)

    assert rejected.state is UploadState.REJECTED
    assert await usage(upload_bench, Home.EU, who.user_id) == (0, 0)
    assert await upload_bench.storage.objects[Home.EU].head(key) is None
    with pytest.raises(AppError) as late:
        await upload_bench.service.complete(who, view.id)
    assert late.value.code == "upload_closed"


async def test_the_sweep_aborts_an_abandoned_upload_and_releases_its_bytes(
    upload_bench: UploadBench, run_slot: RunSlot
) -> None:
    who = person(Home.RU, uuid.uuid4())
    view = await started(upload_bench, who, 4096)
    upload_bench.clock.now += timedelta(hours=24, seconds=1)

    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        await workers.gate.verify_at_start()
        closed = await upload_bench.sweep(workers.transactions).run(Home.RU)

    assert closed == 1
    assert await usage(upload_bench, Home.RU, who.user_id) == (0, 0)
    async with upload_bench.transactions.begin(
        TenancyScope(Home.RU, who.user_id), read_only=True
    ) as session:
        record = await session.get(UploadRecord, view.id)
        pending = (await session.scalars(select(ObjectDeletionRecord))).all()
    assert record is not None
    assert record.state == UploadState.EXPIRED.value
    assert pending == []


async def test_a_ready_upload_is_claimed_once_for_its_purpose_and_a_repeat_answers_the_same(
    upload_bench: UploadBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    view = await started(upload_bench, who, 512)
    await put_part(view, b"z" * 512)
    await upload_bench.service.complete(who, view.id)
    scope = TenancyScope(Home.EU, who.user_id)

    async with upload_bench.transactions.begin(scope) as session:
        first = await upload_bench.claims.claim(session, view.id, UploadPurpose.FILE_MANAGER)
    async with upload_bench.transactions.begin(scope) as session:
        second = await upload_bench.claims.claim(session, view.id, UploadPurpose.FILE_MANAGER)
    with pytest.raises(UploadNotClaimableError):
        async with upload_bench.transactions.begin(scope) as session:
            await upload_bench.claims.claim(session, view.id, UploadPurpose.RECORDING)
    with pytest.raises(UploadNotClaimableError):
        async with upload_bench.transactions.begin(TenancyScope(Home.EU, uuid.uuid4())) as session:
            await upload_bench.claims.claim(session, view.id, UploadPurpose.FILE_MANAGER)

    assert first == second
    assert first.object_key == f"u/{who.user_id}/f/{view.id}"
    assert await usage(upload_bench, Home.EU, who.user_id) == (512, 0)


async def test_the_plan_and_the_purpose_bound_what_may_start(upload_bench: UploadBench) -> None:
    who = person(Home.RU, uuid.uuid4())
    upload_bench.plan.file_manager_gb = 1
    await started(upload_bench, who, GIB - 10)

    with pytest.raises(AppError) as over:
        await started(upload_bench, who, 11)
    upload_bench.plan.file_manager_gb = 0
    with pytest.raises(AppError) as excluded:
        await started(upload_bench, person(Home.RU, uuid.uuid4()), 1)
    with pytest.raises(AppError) as too_large:
        await started(upload_bench, who, 10 * 1024**2 + 1, UploadPurpose.LEO_ATTACHMENT)
    attachment = await started(upload_bench, who, 1024, UploadPurpose.LEO_ATTACHMENT)

    assert (over.value.status, over.value.code) == (413, "storage_limit")
    assert (excluded.value.status, excluded.value.code) == (403, "storage_not_included")
    assert (too_large.value.status, too_large.value.code) == (413, "upload_too_large")
    assert attachment.links[0].request.url
    assert await usage(upload_bench, Home.RU, who.user_id) == (0, GIB - 10)
