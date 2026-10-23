"""Settings > Leo: read and saved field by field, and four switches of the native `/v1/auth/me`.

Nothing is stored until the person changes something; a missing row reads as the defaults.
A change is saved as given and answered whole, so the cabinet's optimistic toggle settles on
what the server kept. A model must be one the plan offers — none before studio publishes
its catalogue, so only `auto` is accepted (ADR 0068 AG-D4).
"""

from collections.abc import Callable, Collection, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final

from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.domain.preferences import (
    PreferenceChanges,
    PreferenceRuleError,
    Preferences,
    ResponseLength,
    check_preferences,
    native_switches,
)
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.identity.contracts import Principal

# Каталог studio ещё не опубликован: модели по имени не предлагаются никому (AG-D4).
NO_MODELS: Final[frozenset[str]] = frozenset()


def preferences_of(record: AgentSettingsRecord | None) -> Preferences:
    """The stored settings, or the defaults when the person never changed any."""
    if record is None:
        return Preferences()
    return Preferences(
        leo_model=record.leo_model,
        response_language=record.response_language,
        response_length=ResponseLength(record.response_length),
        web_search=record.web_search,
        voice_mode=record.voice_mode,
        knowledge_base_search=record.knowledge_base_search,
        connected_services_search=record.connected_services_search,
    )


class AgentPreferences:
    """Reads and writes a person's Settings > Leo."""

    def __init__(
        self,
        transactions: HomeTransactions,
        models: Callable[[], Collection[str]] = lambda: NO_MODELS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._models = models
        self._clock = clock

    async def read(self, scope: TenancyScope) -> Preferences:
        """The person's settings."""
        if scope.user_id is None:
            message = "настройки Leo читаются от имени человека"
            raise ValueError(message)
        async with self._transactions.begin(scope, read_only=True) as session:
            return preferences_of(await session.get(AgentSettingsRecord, scope.user_id))

    async def change(self, principal: Principal, changes: PreferenceChanges) -> Preferences:
        """Apply the fields given, keep the others; refused as a whole when one breaks a rule."""
        async with self._transactions.begin(principal.scope()) as session:
            current = preferences_of(
                await session.get(AgentSettingsRecord, principal.user_id, with_for_update=True)
            )
            try:
                wanted = check_preferences(replace(current, **changes), self._models())
            except PreferenceRuleError as error:
                raise AppError(error.rule.value, HTTPStatus.UNPROCESSABLE_CONTENT) from error
            values = asdict(wanted) | {"updated_at": self._clock()}
            await session.execute(
                insert(AgentSettingsRecord)
                .values(user_id=principal.user_id, **values)
                .on_conflict_do_update(index_elements=[AgentSettingsRecord.user_id], set_=values)
            )
        return wanted

    async def native_me(self, principal: Principal) -> Mapping[str, object]:
        """The four switches of `/v1/auth/me`, by the draft's names."""
        return native_switches(await self.read(principal.scope()))
