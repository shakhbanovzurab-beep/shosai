"""Identity's handler of a person's data: export, erasure's last step, transfer (ADR 0045 p. 7).

Export gives every identity table of the person as JSON Lines — never a hash, a secret or
a token — then the avatar objects. Erasure removes the avatar and export objects, then, in
one home transaction, every identity row of the person and the personal fields of the
account row. The row itself stays, anonymised and `deleted`, because money rows keep
referencing it for 5 years (402-FZ). Only then does the directory free the address, so a
new account with it never meets the old row's email. A transfer copies the account row
first and every identity table after it, objects under their keys; purge removes them
from one home, the account row included, and leaves the directory to the saga.
"""

import hashlib
from collections.abc import AsyncIterator, Mapping
from typing import Any, Final

from sqlalchemy import Delete, delete

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.db.person_rows import (
    PersonRows,
    copy_person_rows,
    person_digest,
    person_lines,
    whole_rows,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.copy import copy_objects
from shosai.core.storage.port import MultipartUploads, ObjectStorage
from shosai.features.identity.application.profile import AVATAR_PREFIX
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.deletion import ERASED_NAME, IDENTITY_OWNER, erased_email
from shosai.features.identity.domain.export import EXPORT_PREFIX
from shosai.features.identity.infrastructure.deletion_records import AccountDeletion
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.export_records import DataExportJob
from shosai.features.identity.infrastructure.records import (
    DirectoryEntry,
    User,
    UserConsent,
    UserIdentity,
)
from shosai.features.identity.infrastructure.session_records import (
    LoginEvent,
    PasswordResetToken,
    RefreshSession,
)

CHUNK_BYTES: Final = 1 << 20
# Таблицы identity, чьи строки человека стираются целиком; `users` обезличивается.
ERASED_TABLES: Final[tuple[Any, ...]] = (
    UserConsent,
    UserIdentity,
    PasswordResetToken,
    RefreshSession,
    LoginEvent,
    DataExportJob,
)
HOME_ROWS: Final = (
    PersonRows(
        User.metadata.tables["users"],
        ("id", "email", "full_name", "display_name", "work_role", "country", "language",
         "timezone", "state", "email_verified_at", "last_login_at", "created_at"),
        key="id", person="id",
    ),
    PersonRows(
        UserConsent.metadata.tables["user_consents"],
        ("kind", "granted", "version", "source", "ip", "user_agent", "recorded_at"), key="id",
    ),
    PersonRows(
        RefreshSession.metadata.tables["refresh_sessions"],
        ("id", "client_kind", "device_label", "ip", "user_agent", "created_at", "last_used_at",
         "expires_at", "revoked_at", "revoke_reason"),
        key="id",
    ),
    PersonRows(
        LoginEvent.metadata.tables["login_events"],
        ("created_at", "outcome", "client_kind", "ip", "user_agent"), key="id",
    ),
    PersonRows(
        PasswordResetToken.metadata.tables["password_reset_tokens"],
        ("created_at", "expires_at", "used_at"), key="token_hash",
    ),
    PersonRows(
        UserIdentity.metadata.tables["user_identities"],
        ("provider", "subject", "email_verified_by_provider", "linked_at", "last_used_at"),
        key="id",
    ),
    PersonRows(
        AccountDeletion.metadata.tables["account_deletions"],
        ("state", "requested_at", "erase_at", "cancelled_at"), key="user_id",
    ),
    PersonRows(
        DataExportJob.metadata.tables["data_export_jobs"],
        ("id", "state", "requested_at", "ready_at", "expires_at", "size_bytes"), key="id",
    ),
)  # fmt: skip
# Что переносится между домами, целыми строками; аккаунт — первым, на него ссылаются.
MOVED: Final = (
    whole_rows(User.metadata.tables["users"], key="id", person="id"),
    *(
        whole_rows(model.metadata.tables[model.__tablename__], key=key)
        for model, key in (
            (UserConsent, "id"), (UserIdentity, "id"), (PasswordResetToken, "token_hash"),
            (RefreshSession, "id"), (LoginEvent, "id"), (AccountDeletion, "user_id"),
            (DataExportJob, "id"),
        )
    ),
)  # fmt: skip
OBJECT_PREFIXES: Final = (AVATAR_PREFIX, EXPORT_PREFIX)
# Каталог живёт в доме ЕС: из него — только дом и состояние, без HMAC адреса.
DIRECTORY_ROWS: Final = PersonRows(
    DirectoryEntry.metadata.tables["directory_entries"],
    ("home", "state", "created_at", "updated_at"),
    key="email_hmac",
)


class IdentityAccountData:
    """The `core.account_data_handlers` binding of identity's tables and objects."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: Directory,
        storage: tuple[Mapping[Home, ObjectStorage], Mapping[Home, MultipartUploads]],
    ) -> None:
        self._transactions = transactions
        self._directory = directory
        self._objects, self._uploads = storage

    @property
    def owner(self) -> str:
        """Identity's declaration."""
        return IDENTITY_OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """The account, its consents, sessions, sign-ins and links, then its avatars."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in HOME_ROWS:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)
        directory = TenancyScope(Home.EU, account.user_id)
        lines = person_lines(self._transactions, directory, DIRECTORY_ROWS, account.user_id)
        yield ExportFile("directory_entries.jsonl", lines)
        storage = self._objects[account.home]
        prefix = f"{AVATAR_PREFIX}{account.user_id}/"
        async for item in storage.list_objects(prefix):
            name = item.key.removeprefix(prefix)
            yield ExportFile(f"avatars/{name}", _object_chunks(storage, item.key))

    async def erase(self, account: AccountRef) -> None:
        """Avatars, archives, identity's rows and the account's personal fields; the address."""
        await self._delete_objects(account)
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            for statement in _erasures(account):
                await session.execute(statement)
            user = await session.get(User, account.user_id, with_for_update=True)
            if user is not None:
                _anonymise(user)
        await self._directory.erase(account.user_id)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """The account row, then every identity table, then the objects under their keys."""
        for rows in MOVED:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )
        for prefix in OBJECT_PREFIXES:
            await copy_objects(
                self._objects[account.home], self._uploads[to_home], f"{prefix}{account.user_id}/"
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each moved table and of each object prefix's keys and sizes."""
        scope = TenancyScope(account.home, account.user_id)
        digests = {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in MOVED
        }
        storage = self._objects[account.home]
        for prefix in OBJECT_PREFIXES:
            listing = hashlib.sha256()
            async for item in storage.list_objects(f"{prefix}{account.user_id}/"):
                listing.update(f"{item.key}:{item.size}\n".encode())
            digests[prefix] = listing.hexdigest()
        return digests

    async def purge(self, account: AccountRef) -> None:
        """Every identity row and object of the account in `account.home`, the account last."""
        await self._delete_objects(account)
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            for statement in _erasures(account):
                await session.execute(statement)
            await session.execute(delete(User).where(User.id == account.user_id))

    async def _delete_objects(self, account: AccountRef) -> None:
        storage = self._objects[account.home]
        for prefix in OBJECT_PREFIXES:
            keys = [item.key async for item in storage.list_objects(f"{prefix}{account.user_id}/")]
            if keys:
                await storage.delete_many(keys)


async def _object_chunks(storage: ObjectStorage, key: str) -> AsyncIterator[bytes]:
    async with storage.open(key) as stream:
        async for chunk in stream.chunks(CHUNK_BYTES):
            yield chunk


def _erasures(account: AccountRef) -> list[Delete]:
    return [delete(model).where(model.user_id == account.user_id) for model in ERASED_TABLES]


def _anonymise(user: User) -> None:
    """Keep the id, the home's language and the dates; nothing that names the person."""
    user.email = erased_email(user.id)
    user.password_hash = None
    user.full_name = ERASED_NAME
    user.display_name = None
    user.work_role = None
    user.country = None
    user.timezone = None
    user.avatar_key = None
    user.last_login_at = None
    user.state = AccountState.DELETED
    user.token_version += 1
