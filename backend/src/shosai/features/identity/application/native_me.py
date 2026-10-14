"""The native `GET /v1/auth/me`: the person, with the parts other slices own (§3.3).

identity owns the account fields. The rest belong to slices built later — the plan and
minutes (billing), recording switches (meetings), memory (memory), Leo's switches
(agent) — and arrive through the `identity.me_contribution` port; until a slice
contributes, its fields keep the draft's defaults, which the desktop clients read as "no
subscription data yet" rather than an error.
"""

from collections.abc import Mapping
from typing import Final

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application import native_errors
from shosai.features.identity.application.operators import held_roles
from shosai.features.identity.application.profile import Profiles
from shosai.features.identity.contracts import ME_CONTRIBUTIONS, Principal
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.registration import ConsentKind
from shosai.features.identity.infrastructure.records import User, UserConsent

# Значения черновика для полей других срезов, пока те не дают своих.
DEFAULTS: Final[Mapping[str, object]] = {
    "no_logs": False,
    "meeting_auto_tasks": False,
    "memory_enabled": True,
    "leo_voice_enabled": True,
    "leo_web_search_enabled": True,
    "leo_kb_search_enabled": True,
    "leo_connector_search_enabled": True,
    "appearance": {},
    "subscription": None,
    "quota": None,
    "features": {},
}
# Статусы черновика: клиенты знают только эти три.
DRAFT_STATUS: Final = {AccountState.FROZEN: "frozen", AccountState.BANNED: "banned"}
# Коды черновика у выпущенных клиентов (ADR 0046): нидерландского они не знают, а null
# читают как «язык системы».
NATIVE_LANGUAGES: Final[Mapping[str, str | None]] = {"pt-BR": "pt", "zh-Hant": "zh", "nl": None}


class NativeMe:
    """Builds the fields of `UserMeResponse` for a person."""

    def __init__(
        self, transactions: HomeTransactions, ports: PortDirectory, profiles: Profiles
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._profiles = profiles

    async def fields(self, principal: Principal) -> dict[str, object]:
        """Every field of the response, identity's and the contributed ones."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            user = await session.get(User, principal.user_id)
            roles = await held_roles(session, principal.user_id)
            marketing = await session.scalar(
                select(UserConsent.granted)
                .where(
                    UserConsent.user_id == principal.user_id,
                    UserConsent.kind == ConsentKind.MARKETING.value,
                )
                .order_by(UserConsent.recorded_at.desc())
                .limit(1)
            )
        if user is None:
            raise native_errors.unauthorized("user_not_found")
        state = AccountState(user.state)
        fields: dict[str, object] = {
            **DEFAULTS,
            "id": str(user.id),
            "email": user.email,
            "username": user.display_name or user.full_name,
            "phone": None,
            "avatar_url": await self._profiles.avatar_url(principal.home, user),
            # Выпущенные клиенты знают две роли: оператор у них — «admin».
            "role": "admin" if roles else "user",
            "status": DRAFT_STATUS.get(state, "active"),
            "is_active": state is AccountState.ACTIVE,
            "last_login_at": user.last_login_at,
            "language": NATIVE_LANGUAGES.get(user.language, user.language),
            "timezone": user.timezone,
            "marketing_consent": bool(marketing),
        }
        for contribution in self._ports.all(ME_CONTRIBUTIONS):
            fields.update(await contribution.native_me(principal))
        return fields
