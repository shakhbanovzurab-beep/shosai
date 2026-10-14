"""The consent journal: every change is a row, the latest row of a kind is current (ID-D2).

It implements the `identity.consent_reader` port: a slice building a `CallContext` asks,
in its own transaction, whether the person consents to transfer abroad, so the answer is
never older than that transaction (rights are not cached, §7).
"""

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.identity.domain.registration import CONSENT_VERSION, ConsentKind
from shosai.features.identity.infrastructure.records import UserConsent


class ConsentJournal:
    """Read and record a person's consents."""

    async def current(self, session: AsyncSession, user_id: UUID) -> dict[ConsentKind, bool]:
        """The latest value of each kind; a kind never recorded reads as not given."""
        rows = await session.execute(
            select(UserConsent.kind, UserConsent.granted)
            .where(UserConsent.user_id == user_id)
            .ext(distinct_on(UserConsent.kind))
            .order_by(UserConsent.kind, UserConsent.recorded_at.desc(), UserConsent.id.desc())
        )
        latest = {ConsentKind(kind): granted for kind, granted in rows.all()}
        return {kind: latest.get(kind, False) for kind in ConsentKind}

    async def cross_border(self, session: AsyncSession, user_id: UUID) -> bool:
        """Whether the person currently consents to transfer to providers abroad."""
        return (await self.current(session, user_id))[ConsentKind.CROSS_BORDER]

    def record(
        self,
        session: AsyncSession,
        user_id: UUID,
        changes: Mapping[ConsentKind, bool],
        client: tuple[str | None, str | None],
    ) -> None:
        """One journal row per changed kind, from the person's settings."""
        ip, user_agent = client
        for kind, granted in changes.items():
            session.add(
                UserConsent(
                    id=new_id(), user_id=user_id, kind=kind.value, granted=granted,
                    version=CONSENT_VERSION, source="settings", ip=ip, user_agent=user_agent,
                )
            )  # fmt: skip
