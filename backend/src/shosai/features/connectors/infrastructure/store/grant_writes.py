"""Writing a grant, its secrets and the app on it in the callback's one transaction.

A grant is upserted by its owner's provider account, so a second app of the same account
joins it and a new token replaces the old one; scopes accumulate, since a provider keeps
what was granted before. An app reconnected with the same account keeps its connection id;
with another account its old connection ends and a new one begins, so a consumer's state of
the first account never mixes with the second's (CN-D2). A grant left with no app is marked
`revoking` for the lifecycle's revocation (plan step 4).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    and_,
    delete,
    exists,
    func,
    literal_column,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.connectors.domain.catalogue import App, AuthKind, Provider
from shosai.features.connectors.domain.states import GrantStatus
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)


@dataclass(frozen=True, slots=True)
class GrantDraft:
    """A grant as the callback learned it."""

    user_id: UUID
    org_id: UUID | None
    provider: Provider
    client_key: str
    auth_kind: AuthKind
    external_account_id: str
    account_label: str | None
    scopes: frozenset[str]
    meta: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SealedSecrets:
    """A grant's ciphertexts and their dates."""

    access_token_enc: bytes | None
    refresh_token_enc: bytes | None
    secret_enc: bytes | None
    expires_at: datetime | None
    keepalive_at: datetime | None


@dataclass(frozen=True, slots=True)
class Attached:
    """What attaching an app changed."""

    connection_id: UUID
    # Прежнее подключение приложения с другим аккаунтом: оно закончилось.
    replaced: UUID | None
    reconnected: bool


# Права копятся: прежние остаются выданными у провайдера; набор без повторов и упорядочен.
MERGED_SCOPES: Final[ColumnElement[list[str]]] = literal_column(
    "ARRAY(SELECT DISTINCT scope FROM unnest("
    "connector_grants.granted_scopes || EXCLUDED.granted_scopes) AS scope ORDER BY scope)"
)


def _owned(
    table: type[ConnectionRecord] | type[GrantRecord], user_id: UUID, org_id: UUID | None
) -> ColumnElement[bool]:
    if org_id is None:
        return and_(table.user_id == user_id, table.org_id.is_(None))
    return table.org_id == org_id


async def held_scopes(
    session: AsyncSession, user_id: UUID, org_id: UUID | None, client_key: str
) -> frozenset[str]:
    """The scopes of the owner's newest grant of one OAuth application, for a union request."""
    query = (
        select(GrantRecord.granted_scopes)
        .where(_owned(GrantRecord, user_id, org_id), GrantRecord.client_key == client_key)
        .order_by(GrantRecord.updated_at.desc())
        .limit(1)
    )
    found = await session.scalar(query)
    return frozenset(found or ())


async def upsert_grant(session: AsyncSession, draft: GrantDraft, secrets: SealedSecrets) -> UUID:
    """The grant of the provider account, created or renewed with its new secrets."""
    values = {
        "user_id": draft.user_id, "org_id": draft.org_id, "provider": draft.provider.value,
        "client_key": draft.client_key, "auth_kind": draft.auth_kind.value,
        "external_account_id": draft.external_account_id, "account_label": draft.account_label,
        "granted_scopes": sorted(draft.scopes), "provider_meta": dict(draft.meta),
    }  # fmt: skip
    inserted = insert(GrantRecord).values(id=new_id(), **values)
    if draft.org_id is None:
        keys = ["user_id", "provider", "client_key", "external_account_id"]
        where = text("org_id IS NULL")
    else:
        keys, where = ["org_id", "provider", "external_account_id"], text("org_id IS NOT NULL")
    statement = inserted.on_conflict_do_update(
        index_elements=keys, index_where=where,
        set_={
            "account_label": inserted.excluded.account_label, "granted_scopes": MERGED_SCOPES,
            "provider_meta": inserted.excluded.provider_meta, "auth_kind": draft.auth_kind.value,
            "status": GrantStatus.ACTIVE.value, "problem": None, "consecutive_failures": 0,
            "updated_at": func.now(),
        },
    ).returning(GrantRecord.id)  # fmt: skip
    grant_id: UUID = (await session.execute(statement)).scalar_one()
    sealed = {
        "user_id": draft.user_id, "org_id": draft.org_id,
        "access_token_enc": secrets.access_token_enc,
        "refresh_token_enc": secrets.refresh_token_enc, "secret_enc": secrets.secret_enc,
        "expires_at": secrets.expires_at, "keepalive_at": secrets.keepalive_at,
        "refreshed_at": func.now(), "refreshing_until": None,
    }  # fmt: skip
    write = insert(GrantSecretRecord).values(grant_id=grant_id, **sealed)
    await session.execute(
        write.on_conflict_do_update(
            index_elements=["grant_id"],
            set_={**sealed, "refresh_generation": GrantSecretRecord.refresh_generation + 1},
        )
    )
    return grant_id


async def attach(
    session: AsyncSession, *, user_id: UUID, org_id: UUID | None, app: App, grant_id: UUID
) -> Attached:
    """Put the app on the grant; a different account's connection of the app ends."""
    current = select(ConnectionRecord.id, ConnectionRecord.grant_id).where(
        _owned(ConnectionRecord, user_id, org_id), ConnectionRecord.app == app.value
    )
    if org_id is not None:
        current = current.where(ConnectionRecord.grant_id == grant_id)
    found = (await session.execute(current.with_for_update())).first()
    if found is not None and found.grant_id == grant_id:
        await session.execute(
            update(ConnectionRecord).where(ConnectionRecord.id == found.id).values(
                status="active", problem=None, updated_at=func.now(),
            )
        )  # fmt: skip
        return Attached(found.id, replaced=None, reconnected=True)
    replaced = None
    if found is not None:
        await session.execute(delete(ConnectionRecord).where(ConnectionRecord.id == found.id))
        await retire_if_orphaned(session, found.grant_id)
        replaced = found.id
    connection_id = new_id()
    session.add(ConnectionRecord(
        id=connection_id, user_id=user_id, org_id=org_id, app=app.value, grant_id=grant_id,
    ))  # fmt: skip
    await session.flush()
    return Attached(connection_id, replaced=replaced, reconnected=False)


async def retire_if_orphaned(session: AsyncSession, grant_id: UUID) -> bool:
    """Mark a grant with no app left for revocation; whether it was marked."""
    statement = (
        update(GrantRecord)
        .where(
            GrantRecord.id == grant_id,
            ~exists().where(ConnectionRecord.grant_id == grant_id),
        )
        .values(status=GrantStatus.REVOKING.value, problem=None, updated_at=func.now())
        .returning(GrantRecord.id)
    )
    return (await session.execute(statement)).first() is not None
