"""A person's own words and model settings in Studio (studio plan §3.5).

The personal context is stored trimmed, ≤ 4 000 characters; nothing saved reads as empty.
The models are the ones the person's plan offers — the snapshot's usable models, frontier
ones only with frontier models on the plan. A role's settings name one of them, able to do
the role, with an output limit the model allows; no model is the role's default. A role the
person never set reads as its default settings.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.identity.contracts import Principal
from shosai.features.studio.application.offers import CatalogueOffers, frontier_on_plan
from shosai.features.studio.contracts import OfferedModel, RoutePerson
from shosai.features.studio.domain.model_settings import checked_settings
from shosai.features.studio.domain.prompts import checked_context
from shosai.features.studio.domain.roles import PromptRole, RoleSettings, default_settings
from shosai.features.studio.infrastructure.person_records import ContextRecord, RoleModelRecord
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot


@dataclass(frozen=True, slots=True)
class PersonalContext:
    """The person's words about themselves; never saved is empty with no time."""

    content: str
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class PersonModels:
    """The models the person may choose and their settings in each of the five roles."""

    models: tuple[OfferedModel, ...]
    roles: tuple[tuple[PromptRole, RoleSettings], ...]


def settings_of(record: RoleModelRecord) -> RoleSettings:
    """The domain's settings of a stored row."""
    return RoleSettings(
        record.model_id, record.temperature, record.max_tokens, reasoning=record.reasoning
    )


class PersonSettings:
    """The personal context and the model settings of a person's roles."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[PlatformSnapshot, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._snapshot, self._ports = sources
        self._offers = CatalogueOffers(self._snapshot)
        self._clock = clock

    async def context(self, principal: Principal) -> PersonalContext:
        """The person's context."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            record = await session.get(ContextRecord, principal.user_id)
        if record is None:
            return PersonalContext("", None)
        return PersonalContext(record.content, record.updated_at)

    async def save_context(self, principal: Principal, content: str) -> PersonalContext:
        """Replace the person's context, trimmed."""
        text, now = checked_context(content), self._clock()
        statement = insert(ContextRecord).values(
            user_id=principal.user_id, content=text, created_at=now, updated_at=now
        )
        async with self._transactions.begin(principal.scope()) as session:
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[ContextRecord.user_id],
                    set_={"content": text, "updated_at": now},
                )
            )
        return PersonalContext(text, now)

    async def models(self, principal: Principal) -> PersonModels:
        """The models on the person's plan and the settings of every role."""
        offered = await self._offers.offered(await self._person(principal))
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = await session.scalars(
                select(RoleModelRecord).where(RoleModelRecord.user_id == principal.user_id)
            )
            stored = {PromptRole(row.role): settings_of(row) for row in rows}
        roles = tuple((role, stored.get(role) or default_settings(role)) for role in PromptRole)
        return PersonModels(offered, roles)

    async def save_role(
        self, principal: Principal, role: PromptRole, settings: RoleSettings
    ) -> RoleSettings:
        """Replace the role's settings, checked against the person's plan and the model."""
        person = await self._person(principal)
        catalogue = await self._snapshot.catalogue()
        model = catalogue.models.get(settings.model_id) if settings.model_id else None
        checked = checked_settings(role, settings, model, frontier_on_plan=frontier_on_plan(person))
        values = {
            "model_id": checked.model_id,
            "temperature": checked.temperature,
            "max_tokens": checked.max_tokens,
            "reasoning": checked.reasoning,
            "updated_at": self._clock(),
        }
        statement = insert(RoleModelRecord).values(
            user_id=principal.user_id, role=role.value, **values
        )
        async with self._transactions.begin(principal.scope()) as session:
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[RoleModelRecord.user_id, RoleModelRecord.role], set_=values
                )
            )
        return checked

    async def _person(self, principal: Principal) -> RoutePerson:
        """The person with their plan; an unreadable plan is 503, never a guess (inv-3)."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(principal.home, principal.user_id)
        return RoutePerson(principal.home, principal.user_id, snapshot)
