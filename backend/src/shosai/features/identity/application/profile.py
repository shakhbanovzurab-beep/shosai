"""The person's profile: names, work role, language, time zone, consents, avatar (§3.4).

A change writes the account row and one consent-journal row per changed consent in one
transaction. The avatar's bytes go to the home's bucket before the transaction that
points at them (no transaction is held across a storage call, §14 rule 8); the old object
is deleted after the commit. The profile also serves the `identity.account_profile_reader`
port: how Leo and the mail of other slices address the person.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.i18n.locales import normalize_language
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.storage.errors import StorageRejectedError, StorageUnavailableError
from shosai.core.storage.port import Disposition, ObjectStorage
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.contracts import AccountProfile, Principal
from shosai.features.identity.domain.avatars import AvatarProblem, check_avatar
from shosai.features.identity.domain.profile import (
    SWITCHABLE,
    WORK_ROLES,
    ProfileProblem,
    clean_name,
    valid_timezone,
    withdrawal_needs_warning,
)
from shosai.features.identity.domain.registration import ConsentKind
from shosai.features.identity.infrastructure.consents import ConsentJournal
from shosai.features.identity.infrastructure.records import User

AVATAR_PREFIX = "avatars/"
STORAGE_FAILURES = (StorageUnavailableError, StorageRejectedError)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProfileView:
    """The profile as Settings shows it."""

    user: User
    home: Home
    consents: dict[ConsentKind, bool]
    avatar_url: str | None


@dataclass(frozen=True, slots=True)
class ProfileChange:
    """The fields a PATCH named; a field it left out keeps its value."""

    names: frozenset[str]
    full_name: str | None = None
    display_name: str | None = None
    work_role: str | None = None
    language: str | None = None
    timezone: str | None = None
    consents: Mapping[ConsentKind, bool] = field(default_factory=dict)
    warning_confirmed: bool = False


class Profiles:
    """Read and change profiles."""

    def __init__(
        self,
        transactions: HomeTransactions,
        journal: ConsentJournal,
        objects: Mapping[Home, ObjectStorage],
    ) -> None:
        self._transactions = transactions
        self._journal = journal
        self._objects = objects

    async def read(self, principal: Principal) -> ProfileView:
        """The person's profile and current consents."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            user = await _user(session, principal.user_id)
            consents = await self._journal.current(session, user.id)
        avatar = await self.avatar_url(principal.home, user)
        return ProfileView(user, principal.home, consents, avatar)

    async def change(
        self, principal: Principal, change: ProfileChange, client: ClientFacts
    ) -> ProfileView:
        """Apply a PATCH; consents changed are journaled, a withdrawal needs its warning."""
        async with self._transactions.begin(principal.scope()) as session:
            user = await _user(session, principal.user_id, lock=True)
            _apply_fields(user, change)
            consents = await self._journal.current(session, user.id)
            changed = {
                kind: wanted
                for kind, wanted in change.consents.items()
                if kind in SWITCHABLE and consents[kind] != wanted
            }
            withdrawing = any(
                withdrawal_needs_warning(kind, current=consents[kind], wanted=wanted)
                for kind, wanted in changed.items()
            )
            if withdrawing and not change.warning_confirmed:
                raise errors.invalid(ProfileProblem.CONSENT_WARNING_REQUIRED.value)
            self._journal.record(session, user.id, changed, (client.ip, client.user_agent))
            consents.update(changed)
        avatar = await self.avatar_url(principal.home, user)
        return ProfileView(user, principal.home, consents, avatar)

    async def set_avatar(self, principal: Principal, data: bytes) -> ProfileView:
        """Store a checked image as the person's avatar."""
        check = check_avatar(data)
        if check.format is None:
            problem = check.problem or AvatarProblem.NOT_AN_IMAGE
            too_large = problem is AvatarProblem.TOO_LARGE
            status = (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                if too_large
                else HTTPStatus.UNPROCESSABLE_ENTITY
            )
            raise AppError(problem.value, status)
        digest = hashlib.sha256(data).hexdigest()[:32]
        key = f"{AVATAR_PREFIX}{principal.user_id}/{digest}.{check.format.extension}"
        await self._objects[principal.home].put(key, data, content_type=check.format.value)
        return await self._point(principal, key)

    async def remove_avatar(self, principal: Principal) -> ProfileView:
        """Remove the avatar; the initials take its place."""
        return await self._point(principal, None)

    async def avatar_url(self, home: Home, user: User) -> str | None:
        """A 15-minute link to the avatar, or None."""
        if user.avatar_key is None:
            return None
        extension = user.avatar_key.rsplit(".", 1)[-1]
        request = await self._objects[home].presign_get(
            user.avatar_key, filename=f"avatar.{extension}", disposition=Disposition.INLINE
        )
        return request.url

    async def profile(self, session: AsyncSession, user_id: UUID) -> AccountProfile | None:
        """The `identity.account_profile_reader` port: how to address the person."""
        user = await session.get(User, user_id)
        if user is None:
            return None
        return AccountProfile(
            user.display_name or user.full_name, user.language, user.timezone, user.country,
            user.email,
        )  # fmt: skip

    async def _point(self, principal: Principal, key: str | None) -> ProfileView:
        async with self._transactions.begin(principal.scope()) as session:
            user = await _user(session, principal.user_id, lock=True)
            previous, user.avatar_key = user.avatar_key, key
            consents = await self._journal.current(session, user.id)
        if previous is not None and previous != key:
            try:
                await self._objects[principal.home].delete(previous)
            except STORAGE_FAILURES:
                # Сирота в бакете безвредна: её подберёт стирание по префиксу аккаунта.
                log.warning("Прежний аватар не удалён", user_id=str(principal.user_id))
        avatar = await self.avatar_url(principal.home, user)
        return ProfileView(user, principal.home, consents, avatar)


async def _user(session: AsyncSession, user_id: UUID, *, lock: bool = False) -> User:
    user = await session.get(User, user_id, with_for_update=lock)
    if user is None:
        raise AppError("user_not_found", HTTPStatus.UNAUTHORIZED)
    return user


def _apply_fields(user: User, change: ProfileChange) -> None:
    if "full_name" in change.names:
        name = clean_name(change.full_name or "")
        if name is None:
            raise errors.invalid(ProfileProblem.BLANK_NAME.value)
        user.full_name = name
    if "display_name" in change.names:
        user.display_name = clean_name(change.display_name or "")
    if "work_role" in change.names:
        if change.work_role is not None and change.work_role not in WORK_ROLES:
            raise errors.invalid(ProfileProblem.UNKNOWN_WORK_ROLE.value)
        user.work_role = change.work_role
    if "language" in change.names:
        language = normalize_language(change.language)
        if language is None:
            raise errors.invalid("unsupported_language")
        user.language = language
    if "timezone" in change.names:
        if change.timezone is not None and not valid_timezone(change.timezone):
            raise errors.invalid(ProfileProblem.UNKNOWN_TIMEZONE.value)
        user.timezone = change.timezone
    user.updated_at = datetime.now(UTC)
