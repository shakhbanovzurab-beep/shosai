"""Identity's erasure handler: the last step of the saga (ID-D5, ADR 0045 point 7).

It removes the avatar objects, then, in one home transaction, every identity row of the
person and the personal fields of the account row. The row itself stays, anonymised and
`deleted`, because money rows keep referencing it for 5 years (402-FZ). Only then does the
directory free the address, so a new account with it never meets the old row's email.
"""

from collections.abc import Mapping
from typing import Any, Final

from sqlalchemy import Delete, delete

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.storage.port import ObjectStorage
from shosai.features.identity.application.profile import AVATAR_PREFIX
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.deletion import ERASED_NAME, IDENTITY_OWNER, erased_email
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User, UserConsent, UserIdentity
from shosai.features.identity.infrastructure.session_records import (
    LoginEvent,
    PasswordResetToken,
    RefreshSession,
)

# Таблицы identity, чьи строки человека стираются целиком; `users` обезличивается.
ERASED_TABLES: Final[tuple[Any, ...]] = (
    UserConsent,
    UserIdentity,
    PasswordResetToken,
    RefreshSession,
    LoginEvent,
)


class IdentityAccountData:
    """The `core.account_data_handlers` binding of identity's tables and avatars."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: Directory,
        objects: Mapping[Home, ObjectStorage],
    ) -> None:
        self._transactions = transactions
        self._directory = directory
        self._objects = objects

    @property
    def owner(self) -> str:
        """Identity's declaration."""
        return IDENTITY_OWNER

    async def erase(self, account: AccountRef) -> None:
        """Avatars, identity's rows and the account's personal fields; then the address."""
        storage = self._objects[account.home]
        prefix = f"{AVATAR_PREFIX}{account.user_id}/"
        keys = [item.key async for item in storage.list_objects(prefix)]
        if keys:
            await storage.delete_many(keys)
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            for statement in _erasures(account):
                await session.execute(statement)
            user = await session.get(User, account.user_id, with_for_update=True)
            if user is not None:
                _anonymise(user)
        await self._directory.erase(account.user_id)


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
