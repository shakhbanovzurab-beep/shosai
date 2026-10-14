"""Desktop sign-in through the browser (ADR 0045 points 7, 9; §3.6 "Desktop sign-in").

1. The app opens `/app/connect?state=…[&code_challenge=…]`; the signed-in browser asks
   the person to confirm, then calls `POST /v1/auth/desktop/code` with the challenge.
2. The page sends the browser to `shosai://auth?code&state`.
3. The app exchanges the code (and the verifier, if it sent a challenge) for its own
   desktop family; its refresh token travels in the body, never in a cookie.
"""

from dataclasses import dataclass
from http import HTTPStatus

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.application import native_errors
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.contracts import Principal
from shosai.features.identity.domain.accounts import AccountState, sign_in_refusal
from shosai.features.identity.domain.pkce import S256, valid_challenge, verifier_matches
from shosai.features.identity.domain.sessions import ClientKind
from shosai.features.identity.infrastructure.desktop_codes import (
    CODE_LIFETIME,
    DesktopCodes,
    DesktopCodesUnavailableError,
    DesktopGrant,
)
from shosai.features.identity.infrastructure.records import User


@dataclass(frozen=True, slots=True)
class IssuedCode:
    """The one-time code and its lifetime in seconds."""

    code: str
    expires_in: int


class DesktopSignIn:
    """Codes for the desktop app and their exchange."""

    def __init__(
        self, transactions: HomeTransactions, codes: DesktopCodes, sessions: Sessions
    ) -> None:
        self._transactions = transactions
        self._codes = codes
        self._sessions = sessions

    async def issue(
        self, principal: Principal, challenge: str | None, method: str | None
    ) -> IssuedCode:
        """A code for the signed-in person, bound to the app's challenge if it sent one."""
        if challenge is not None and (method != S256 or not valid_challenge(challenge)):
            raise AppError("invalid_code_challenge", HTTPStatus.UNPROCESSABLE_ENTITY)
        grant = DesktopGrant(principal.user_id, principal.home, challenge)
        try:
            code = await self._codes.issue(grant)
        except DesktopCodesUnavailableError as error:
            raise unavailable() from error
        return IssuedCode(code, int(CODE_LIFETIME.total_seconds()))

    async def exchange(self, code: str, verifier: str | None, client: ClientFacts) -> IssuedTokens:
        """The app's own session for a live code; the code is spent whatever the outcome."""
        try:
            grant = await self._codes.take(code)
        except DesktopCodesUnavailableError as error:
            raise unavailable() from error
        if grant is None:
            raise native_errors.invalid_desktop_code()
        if grant.challenge is not None and not verifier_matches(grant.challenge, verifier):
            raise native_errors.invalid_desktop_code()
        scope = TenancyScope(grant.home, grant.user_id)
        async with self._transactions.begin(scope) as session:
            user = await session.get(User, grant.user_id)
            if user is None:
                raise native_errors.invalid_desktop_code()
            refusal = sign_in_refusal(AccountState(user.state))
            if refusal is not None:
                raise native_errors.refused(refusal)
            return await self._sessions.open(session, user, grant.home, ClientKind.DESKTOP, client)

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        """Rotate the app's family; refusals carry the desktop refresh's `detail`."""
        return await self._sessions.refresh(refresh_token, native_errors.desktop_unauthorized)


def unavailable() -> AppError:
    """503: Valkey, which keeps the codes, did not answer."""
    return AppError(
        "desktop_sign_in_unavailable",
        HTTPStatus.SERVICE_UNAVAILABLE,
        params={"retry_after_seconds": 5},
    )
