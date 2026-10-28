"""The operator's platform layer: one draft, published as numbered versions (ST-D1, ADR 0074).

The draft is saved whole or by section, last write wins — there is one operator (ADR 0049).
A publish locks the draft's row, so two publishes take consecutive numbers, cleans and checks
the draft, writes the version and resets the draft to it; a restore publishes a copy of an old
version the same way. Each runs once per `Idempotency-Key`: a retry returns the version the
first run wrote. This process's snapshot is dropped after a publish; every other process reads
the new version within a minute.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import EffectKey, EffectLedger, EffectScope
from shosai.core.kernel.ids import new_id
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.page import PageRequest
from shosai.features.studio.application.catalogue_admin import EU
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.platform_layer import (
    BUILT_IN,
    FeaturePrompt,
    PlatformConfig,
    PlatformFeature,
    SafetyRule,
)
from shosai.features.studio.domain.versions import Publication, Version, publication, restoration
from shosai.features.studio.infrastructure.platform_config_codec import config_json, config_of
from shosai.features.studio.infrastructure.platform_records import (
    PlatformDraftRecord,
    PlatformVersionRecord,
)
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot

PUBLISH: Final = EffectScope("studio.platform_publish", timedelta(days=1))
RESTORE: Final = EffectScope("studio.platform_restore", timedelta(days=1))
DRAFT_ID: Final = 1


class Position(BaseModel):
    """Where a page of versions ended: the last number it returned."""

    number: int


VERSIONS: Final = CursorCodec("studio.platform_versions", Position)


class PublishedRef(BaseModel):
    """What a publish or a restore stores for its retry: the version it wrote."""

    version_id: UUID


@dataclass(frozen=True, slots=True)
class Draft:
    """The draft and when it was last saved; never saved is the live version's config."""

    config: PlatformConfig
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class PromptsState:
    """The draft and the live version, none before the first publish."""

    draft: Draft
    published: Version | None


@dataclass(frozen=True, slots=True)
class DraftChanges:
    """The sections a save replaces; a section left None stays."""

    system_prompt: str | None = None
    rules: tuple[SafetyRule, ...] | None = None
    blocked_topics: tuple[str, ...] | None = None
    features: Mapping[PlatformFeature, FeaturePrompt] | None = None


def version_of(record: PlatformVersionRecord) -> Version:
    """The domain's version of a row."""
    return Version(
        record.id,
        record.number,
        config_of(record.config),
        record.comment,
        record.published_at,
        record.restored_from,
    )


def changed(config: PlatformConfig, changes: DraftChanges) -> PlatformConfig:
    """The config with the given sections replaced whole."""
    features = config.features
    if changes.features is not None:
        features = {**config.features, **changes.features}
    return replace(
        config,
        system_prompt=config.system_prompt
        if changes.system_prompt is None
        else changes.system_prompt,
        rules=config.rules if changes.rules is None else changes.rules,
        blocked_topics=config.blocked_topics
        if changes.blocked_topics is None
        else changes.blocked_topics,
        features=features,
    )


async def live(session: AsyncSession) -> Version | None:
    """The newest version, the one every process serves."""
    record = await session.scalar(
        select(PlatformVersionRecord).order_by(PlatformVersionRecord.number.desc()).limit(1)
    )
    return version_of(record) if record is not None else None


class PlatformPrompts:
    """The draft, publish, restore and the versions of the platform layer."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[EffectLedger, PlatformSnapshot],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects, self._snapshot = sources
        self._clock = clock

    async def state(self) -> PromptsState:
        """The draft and the live version."""
        async with self._transactions.begin(EU, read_only=True) as session:
            published = await live(session)
            record = await session.get(PlatformDraftRecord, DRAFT_ID)
        if record is None:
            config = published.config if published is not None else BUILT_IN
            return PromptsState(Draft(config, None), published)
        return PromptsState(Draft(config_of(record.config), record.updated_at), published)

    async def save_draft(self, changes: DraftChanges) -> Draft:
        """Replace the given sections of the draft."""
        now = self._clock()
        async with self._transactions.begin(EU) as session:
            record = await session.get(PlatformDraftRecord, DRAFT_ID, with_for_update=True)
            if record is None:
                published = await live(session)
                base = published.config if published is not None else BUILT_IN
                record = PlatformDraftRecord(id=DRAFT_ID, config=config_json(base))
                session.add(record)
            config = changed(config_of(record.config), changes)
            record.config, record.updated_at = config_json(config), now
        return Draft(config, now)

    async def publish(self, comment: str, key: EffectKey) -> PromptsState:
        """Publish the draft as the next version, once per key."""

        async def effect(session: AsyncSession) -> PublishedRef:
            record = await session.get(PlatformDraftRecord, DRAFT_ID, with_for_update=True)
            draft = config_of(record.config) if record is not None else BUILT_IN
            return await self._write(session, publication(draft, await live(session), comment))

        return await self._once(key, effect)

    async def restore(self, version_id: UUID, comment: str, key: EffectKey) -> PromptsState:
        """Publish a copy of an old version as the next one, once per key."""

        async def effect(session: AsyncSession) -> PublishedRef:
            await session.get(PlatformDraftRecord, DRAFT_ID, with_for_update=True)
            old = await session.get(PlatformVersionRecord, version_id)
            current = await live(session)
            if old is None or current is None:
                raise StudioRuleError(StudioRule.VERSION_NOT_FOUND)
            return await self._write(session, restoration(version_of(old), current, comment))

        return await self._once(key, effect)

    async def versions(self, page: PageRequest) -> tuple[tuple[Version, ...], str | None]:
        """Versions, newest first, by cursor."""
        statement = select(PlatformVersionRecord).order_by(PlatformVersionRecord.number.desc())
        if page.cursor is not None:
            statement = statement.where(
                PlatformVersionRecord.number < VERSIONS.decode(page.cursor).number
            )
        async with self._transactions.begin(EU, read_only=True) as session:
            rows = (await session.scalars(statement.limit(page.limit + 1))).all()
        found = tuple(version_of(row) for row in rows[: page.limit])
        more = len(rows) > page.limit
        return found, VERSIONS.encode(Position(number=found[-1].number)) if more and found else None

    async def version(self, version_id: UUID) -> Version:
        """One version whole."""
        async with self._transactions.begin(EU, read_only=True) as session:
            record = await session.get(PlatformVersionRecord, version_id)
        if record is None:
            raise StudioRuleError(StudioRule.VERSION_NOT_FOUND)
        return version_of(record)

    async def _once(
        self, key: EffectKey, effect: Callable[[AsyncSession], Awaitable[PublishedRef]]
    ) -> PromptsState:
        async with self._transactions.begin(EU) as session:
            await self._effects.once(session, key, PublishedRef, lambda: effect(session))
        self._snapshot.drop()
        return await self.state()

    async def _write(self, session: AsyncSession, published: Publication) -> PublishedRef:
        """The version, and the draft reset to it."""
        version_id, now = new_id(), self._clock()
        document = config_json(published.config)
        session.add(
            PlatformVersionRecord(
                id=version_id,
                number=published.number,
                config=document,
                comment=published.comment,
                restored_from=published.restored_from,
                published_at=now,
            )
        )
        record = await session.get(PlatformDraftRecord, DRAFT_ID)
        if record is None:
            session.add(PlatformDraftRecord(id=DRAFT_ID, config=document, updated_at=now))
        else:
            record.config, record.updated_at = document, now
        await session.flush()
        return PublishedRef(version_id=version_id)
