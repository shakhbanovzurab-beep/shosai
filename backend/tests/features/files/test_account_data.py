"""Files' part of a person's export, transfer and erasure: rows and objects by pointer."""

import uuid
from collections.abc import Mapping

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.application.account_data import FilesAccountData
from shosai.features.files.domain.keys import PersonOwner, file_key, held_key, preview_key
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.files.infrastructure.held_records import HeldObjectRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from tests.core.storage.adapters import slot_storage
from tests.harness.database_access import DatabaseAccess
from tests.harness.shared_services import SlotBucket

LEGACY_KEY = "u-0190f0f0/0190f0f0-0000-7000-8000-00000000f001/old report.pdf"


async def test_export_transfer_and_erasure_follow_the_pointers_and_spare_workspace_files(
    homes: DatabaseAccess, buckets: Mapping[Home, SlotBucket]
) -> None:
    storages = {home: slot_storage(bucket) for home, bucket in buckets.items()}
    objects = {home: storage.objects for home, storage in storages.items()}
    uploads = {home: storage.uploads for home, storage in storages.items()}
    handler = FilesAccountData(homes.transactions, (objects, uploads))
    person, workspace = uuid.uuid4(), uuid.uuid4()
    own, shared_key, kept_key = (
        file_key(PersonOwner(person), uuid.uuid4()),
        file_key(PersonOwner(person), uuid.uuid4()),
        file_key(PersonOwner(person), uuid.uuid4()),
    )
    held = uuid.uuid4()
    attached, preview = held_key(PersonOwner(person), held), preview_key(PersonOwner(person), held)
    for key, body in (
        (attached, b"attached"),
        (preview, b"preview"),
        (own, b"own"),
        (shared_key, b"copied"),
        (kept_key, b"handed over"),
        (LEGACY_KEY, b"legacy"),
    ):
        await objects[Home.RU].put(key, body, content_type="application/pdf")
    folder = uuid.uuid4()

    def row(key: str, **fields: object) -> StorageFileRecord:
        return StorageFileRecord(
            id=uuid.uuid4(), user_id=person, name="Report.pdf", content_type="application/pdf",
            size_bytes=3, object_key=key, **fields,
        )  # fmt: skip

    async with homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(FileFolderRecord(id=folder, user_id=person, name="Work"))
        session.add(StorageUsageRecord(user_id=person, used_bytes=12))
        session.add_all([row(own, folder_id=folder), row(LEGACY_KEY), row(shared_key)])
        # Вложение задачи держит свой объект с превью; копия файла делит объект с ним.
        session.add_all([
            HeldObjectRecord(
                id=held, user_id=person, holder="task_attachment", object_key=attached,
                preview_key=preview, preview_state="made", filename="Схема.png",
                content_type="image/png", size_bytes=8,
            ),
            HeldObjectRecord(
                id=uuid.uuid4(), user_id=person, holder="task_attachment", object_key=own,
                filename="Report.pdf", content_type="application/pdf", size_bytes=3,
            ),
        ])  # fmt: skip
    async with homes.transactions.begin(TenancyScope(Home.RU, person, workspace)) as session:
        # Переданный пространству файл и копия в нём держат ключи под префиксом человека.
        session.add(row(kept_key, org_id=workspace, access="organization"))
        session.add(row(shared_key, org_id=workspace, access="organization"))
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    exported = {
        item.name: b"".join([chunk async for chunk in item.chunks])
        async for item in handler.export(russian)
    }
    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    same = await handler.manifest(russian) == await handler.manifest(european)
    await handler.erase(russian)
    await handler.purge(european)

    assert {
        "storage_files.jsonl",
        "file_folders.jsonl",
        "uploads.jsonl",
        "storage_usage.jsonl",
        "held_objects.jsonl",
    } <= set(exported)
    assert sorted(body for name, body in exported.items() if name.startswith("held/")) == [
        b"attached", b"own",
    ]  # fmt: skip
    assert sorted(body for name, body in exported.items() if name.startswith("files/")) == [
        b"copied", b"legacy", b"own",
    ]  # fmt: skip
    assert same
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) == ()
    assert await objects[Home.RU].head(own) is None
    assert await objects[Home.RU].head(attached) is None
    assert await objects[Home.RU].head(preview) is None
    assert await objects[Home.RU].head(LEGACY_KEY) is None
    assert await objects[Home.RU].head(kept_key) is not None
    assert await objects[Home.RU].head(shared_key) is not None
