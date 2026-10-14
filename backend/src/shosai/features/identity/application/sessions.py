"""Opening, refreshing and revoking refresh families (ADR 0045 point 1; draft spec 022).

A family is opened inside the transaction that proves the person (sign-in, a confirmed
registration), so its row commits with that proof. A refresh locks its family's row,
judges the presented token and rotates it; a replayed old token revokes the family, and
that revocation is committed before the 401 so the theft signal is never rolled back
(draft lesson). Access tokens live 30 minutes; a family slides to 7 days on each refresh.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application import native_errors
from shosai.features.identity.application.deletion import DeletionWindow
from shosai.features.identity.application.native_errors import RefreshErrors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.domain.accounts import AccountState, sign_in_refusal
from shosai.features.identity.domain.sessions import (
    ClientKind,
    FamilyState,
    RotationVerdict,
    judge,
    token_id,
    token_id_hash,
)
from shosai.features.identity.domain.tokens import (
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    AccessClaims,
    InvalidTokenError,
    RefreshClaims,
)
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import User
from shosai.features.identity.infrastructure.session_records import RefreshSession
from shosai.features.identity.infrastructure.token_codec import TokenCodec

ACCESS_SECONDS: Final = int(ACCESS_TOKEN_LIFETIME.total_seconds())
DEVICE_LABEL_LENGTH: Final = 128


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    """An access token, its lifetime in seconds, and the family's current refresh token."""

    access_token: str
    expires_in: int
    refresh_token: str
    family_id: UUID


@dataclass(frozen=True, slots=True)
class FamilyToken:
    """The refresh token a family hands out now: its id and the family's expiry."""

    family_id: UUID
    current_id: str
    expires_at: datetime


class Sessions:
    """The refresh families of every account."""

    def __init__(
        self,
        transactions: HomeTransactions,
        directory: Directory,
        codec: TokenCodec,
        id_key: bytes,
        window: DeletionWindow,
    ) -> None:
        self._transactions = transactions
        self._directory = directory
        self._codec = codec
        self._id_key = id_key
        self._window = window

    async def open(
        self, session: AsyncSession, user: User, home: Home, kind: ClientKind, client: ClientFacts
    ) -> IssuedTokens:
        """A new family for a proven person, written in the caller's transaction.

        A sign-in during the deletion window cancels the deletion first (ID-D5).
        """
        await self._window.cancel_if_scheduled(session, user)
        now = datetime.now(UTC)
        family_id = new_id()
        current = token_id(self._id_key, family_id, 0)
        session.add(
            RefreshSession(
                id=family_id, user_id=user.id, client_kind=kind.value, generation=0,
                current_id_hash=token_id_hash(current), expires_at=now + REFRESH_TOKEN_LIFETIME,
                ip=client.ip, user_agent=client.user_agent, device_label=_label(client.user_agent),
            )
        )  # fmt: skip
        return self._issue(
            user, home, FamilyToken(family_id, current, now + REFRESH_TOKEN_LIFETIME), now
        )

    async def refresh(
        self, refresh_token: str, errors: RefreshErrors = native_errors.unauthorized
    ) -> IssuedTokens:
        """Rotate the family of a valid refresh token, or answer the draft's 401 or 403.

        `errors` gives each refusal the `detail` its route's clients read: the web refresh
        and the desktop refresh of the draft spell them differently.
        """
        claims = self._claims(refresh_token, errors)
        home = claims.home or await self._directory.home_of(claims.user_id)
        if home is None:
            raise errors("user_not_found")
        async with self._transactions.begin(TenancyScope(home, claims.user_id)) as session:
            user = await session.get(User, claims.user_id)
            if user is None:
                raise errors("user_not_found")
            refusal = sign_in_refusal(AccountState(user.state))
            if refusal is not None:
                raise native_errors.refused(refusal)
            if claims.token_version != user.token_version:
                raise errors("token_revoked")
            family = await session.get(RefreshSession, claims.family_id, with_for_update=True)
            if family is None or family.user_id != user.id:
                raise errors("refresh_invalid")
            now = datetime.now(UTC)
            verdict = judge(_state(family), claims.token_id, now)
            if verdict is not RotationVerdict.REUSE:
                return self._advance(_Turn(user, home, family, verdict, now), errors)
            # Старый токен вне окна — кража: семейство отзывается коммитом, и только потом 401.
            family.revoked_at, family.revoke_reason = now, "reuse"
        raise errors("refresh_invalid")

    async def revoke(self, refresh_token: str, reason: str) -> bool:
        """End the family of a refresh token, if it is valid; False otherwise."""
        try:
            claims = self._codec.decode_refresh(refresh_token)
        except InvalidTokenError:
            return False
        home = claims.home or await self._directory.home_of(claims.user_id)
        if home is None:
            return False
        async with self._transactions.begin(TenancyScope(home, claims.user_id)) as session:
            result = await session.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.id == claims.family_id,
                    RefreshSession.user_id == claims.user_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC), revoke_reason=reason)
            )
        return bool(getattr(result, "rowcount", 0))

    def _advance(self, turn: _Turn, errors: RefreshErrors) -> IssuedTokens:
        user, home, family, verdict, now = (
            turn.user,
            turn.home,
            turn.family,
            turn.verdict,
            turn.now,
        )
        if verdict is RotationVerdict.REVOKED:
            raise errors("token_revoked")
        if verdict is RotationVerdict.EXPIRED:
            raise errors("refresh_expired")
        current = token_id(self._id_key, family.id, family.generation)
        if verdict is RotationVerdict.GRACE and token_id_hash(current) == family.current_id_hash:
            # Вторая вкладка в окне 10 с получает текущий токен, вращения нет.
            return self._issue(user, home, FamilyToken(family.id, current, family.expires_at), now)
        family.generation += 1
        following = token_id(self._id_key, family.id, family.generation)
        family.previous_id_hash = family.current_id_hash
        family.current_id_hash = token_id_hash(following)
        family.rotated_at = now
        family.last_used_at = now
        family.expires_at = now + REFRESH_TOKEN_LIFETIME
        return self._issue(user, home, FamilyToken(family.id, following, family.expires_at), now)

    def _issue(self, user: User, home: Home, token: FamilyToken, now: datetime) -> IssuedTokens:
        access = AccessClaims(
            user.id, home, user.token_version, now, now + ACCESS_TOKEN_LIFETIME, token.family_id
        )
        refresh = RefreshClaims(
            user.id, home, user.token_version, token.family_id, token.current_id, now,
            token.expires_at,
        )  # fmt: skip
        return IssuedTokens(
            access_token=self._codec.encode_access(access),
            expires_in=ACCESS_SECONDS,
            refresh_token=self._codec.encode_refresh(refresh),
            family_id=token.family_id,
        )

    def _claims(self, refresh_token: str, errors: RefreshErrors) -> RefreshClaims:
        try:
            return self._codec.decode_refresh(refresh_token)
        except InvalidTokenError as error:
            code = "refresh_expired" if error.reason == "expired" else "refresh_invalid"
            raise errors(code) from error


@dataclass(frozen=True, slots=True)
class _Turn:
    """A refresh being judged: whose family, which verdict, at what time."""

    user: User
    home: Home
    family: RefreshSession
    verdict: RotationVerdict
    now: datetime


def _state(family: RefreshSession) -> FamilyState:
    return FamilyState(
        current_id_hash=family.current_id_hash,
        previous_id_hash=family.previous_id_hash,
        rotated_at=family.rotated_at,
        expires_at=family.expires_at,
        revoked=family.revoked_at is not None,
    )


def _label(user_agent: str | None) -> str | None:
    # Подпись устройства в списке сессий: начало строки клиента, до 128 символов.
    return user_agent[:DEVICE_LABEL_LENGTH] if user_agent else None
