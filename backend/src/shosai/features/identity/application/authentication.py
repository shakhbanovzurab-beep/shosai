"""The authenticator: a bearer token becomes the person it acts for (ADR 0045 point 2).

One implementation for HTTP and WebSocket (draft lesson AUTH-01: two copies drifted into
a privilege escalation). No database read: the signature and claims are checked locally,
the home comes from the token (or, for the draft's tokens without one, from the cached
directory), and revocations arrive through the account-state marker in Valkey.
"""

from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.features.identity.application import native_errors
from shosai.features.identity.contracts import Principal
from shosai.features.identity.domain.accounts import AccountState, SignInRefusal
from shosai.features.identity.domain.tokens import InvalidTokenError
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.token_codec import TokenCodec

REFUSED_STATES = {
    AccountState.BANNED: SignInRefusal.BANNED,
    AccountState.FROZEN: SignInRefusal.FROZEN,
}
REVOKED_STATES = frozenset(
    {AccountState.DELETION_SCHEDULED, AccountState.DELETING, AccountState.DELETED}
)


class TokenAuthenticator:
    """The `identity.authenticator` port."""

    def __init__(self, codec: TokenCodec, directory: Directory, markers: AccountMarkers) -> None:
        self._codec = codec
        self._directory = directory
        self._markers = markers

    async def principal(self, bearer_token: str) -> Principal:
        """The person of a valid access token, or the draft's 401 or 403."""
        try:
            claims = self._codec.decode_access(bearer_token)
        except InvalidTokenError as error:
            code = "token_expired" if error.reason == "expired" else "token_invalid"
            raise native_errors.unauthorized(code) from error
        home = claims.home or await self._home_of(claims.user_id)
        reading = await self._markers.read(claims.user_id, claims.family_id)
        marker = reading.account
        if marker is not None:
            if marker.state in REFUSED_STATES:
                raise native_errors.refused(REFUSED_STATES[marker.state])
            if claims.token_version < marker.token_version or marker.state in REVOKED_STATES:
                raise native_errors.unauthorized("token_revoked")
        if reading.family_revoked:
            raise native_errors.unauthorized("token_revoked")
        return Principal(claims.user_id, home, claims.token_version, claims.family_id)

    async def _home_of(self, user_id: UUID) -> Home:
        home = await self._directory.home_of(user_id)
        if home is None:
            raise native_errors.unauthorized("user_not_found")
        return home
