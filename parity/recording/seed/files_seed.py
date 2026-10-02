"""Files of the `lead` persona: a folder tree, files of different kinds and share links; quotas.

The files are not in storage: the parity stand has no S3. The draft serves lists, search,
share links and quotas from the database; preview and download go to S3, so the state
defines those responses.

The draft takes used storage from the user's counter, not from the file rows: the
scheduler reconciles the counter, and it is disabled on the stand. The seed sets the
counter of `lead` to the sum of its files (including room recordings and the estimate
from the hubs seed) as the last step. The quota personas (`quota`, `overquota`) have no
files: 92 % of the Pro tariff limit, and over the limit since July 12.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from meetassist.models.storage import StorageFile
from meetassist.models.user import User
from meetassist.services.auth_service import hash_password
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import FILE_SHARES, SHARE_PASSWORD

GIB = 1024**3
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class _Item:
    """A folder (mime None) or a file; `share` is the share link key in ids.json."""

    name: str
    size: int = 0
    mime: str | None = None
    children: tuple[_Item, ...] = field(default_factory=tuple)
    share: str | None = None
    password: bool = False
    expires_days: int | None = None
    download_disabled: bool = False

    @property
    def is_folder(self) -> bool:
        return self.mime is None


_TREE = (
    _Item("Acme", share="folder", children=(
        _Item("Договор", children=(
            _Item("Договор_Acme_2026.pdf", 1_245_184, PDF),
            _Item("Приложение_1_SLA.docx", 86_528, DOCX),
        )),
        _Item("Встречи", children=(
            _Item("Демо_Acme.mp4", 734_003_200, "video/mp4"),
            _Item("Планирование_Q4.mp3", 18_874_368, "audio/mpeg"),
        )),
        _Item("Логотип_Acme.png", 214_016, "image/png"),
    )),
    _Item("Проекты", share="folderLocked", password=True, children=(
        _Item("Портал", children=(_Item("Скрипты", children=(_Item("migrate_users.py", 6_144, "text/x-python"),)),)),
        _Item("Архив_пилота_2025.zip", 52_428_800, "application/zip"),
    )),
    _Item("Личное"),
    _Item("Заметки.txt", 2_048, "text/plain"),
    _Item("Презентация_Q3.pdf", 4_718_592, PDF, share="fileLocked", password=True, expires_days=7),
    _Item("Скриншот_дашборда.jpg", 512_000, "image/jpeg", share="fileView", download_disabled=True),
    _Item("Прайс_2025.pdf", 731_136, PDF, share="fileExpired", expires_days=-2),
)

#: Персоны квот: занятые байты и начало перебора.
_QUOTAS = {"quota": (98_784_247_808, None), "overquota": (120_259_084_288, timedelta(days=5))}


async def seed_files(db: AsyncSession, owner: User, clock: datetime) -> None:
    """The owner's file tree; created more than a day before the parity clock."""
    counter = 0

    def add(items: tuple[_Item, ...], parent: uuid.UUID | None) -> None:
        nonlocal counter
        for item in items:
            counter += 1
            row_id = uuid.uuid4()
            created = clock - timedelta(days=30, minutes=-counter)
            row = StorageFile(id=row_id, owner_id=owner.id, name=item.name, is_folder=item.is_folder, parent_id=parent,
                              s3_key=None if item.is_folder else f"parity/{row_id}", size=item.size,
                              mime_type=item.mime, created_at=created)
            if item.share is not None:
                row.share_token = FILE_SHARES[item.share]
                row.share_password_hash = hash_password(SHARE_PASSWORD) if item.password else None
                row.share_expires_at = None if item.expires_days is None else clock + timedelta(days=item.expires_days)
                row.share_download_disabled = item.download_disabled
            db.add(row)
            add(item.children, row_id)

    add(_TREE, None)
    await db.flush()


async def set_storage_counters(db: AsyncSession, accounts: dict[str, User], clock: datetime) -> None:
    """Used storage counters: the sum of its files for `lead`, set values for the quota personas."""
    lead = accounts["lead"]
    lead.storage_used_bytes = int(await db.scalar(
        select(func.coalesce(func.sum(StorageFile.size), 0)).where(StorageFile.owner_id == lead.id)) or 0)
    for key, (used, over_for) in _QUOTAS.items():
        accounts[key].storage_used_bytes = used
        accounts[key].storage_over_limit_since = None if over_for is None else clock - over_for
    await db.flush()
