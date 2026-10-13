"""Apply an effect once per key, in the caller's transaction (§10, inv-9; Leo §8.4 rule 2).

`EffectLedger.once` claims the key, runs the effect and records its outcome in the session
the caller opened, so the key, the effect and the outcome commit together or not at all.
A repeat of the key — a retried request, a redelivered task, a second click — returns the
stored outcome and writes nothing. Two transactions with one key never both apply it: the
second waits on the first one's row and then reads its outcome.

A key past its `keep` is forgotten even before the purge removes it: the next use takes it
over as new. The same key with a different request is the client's error
(`idempotency_key_reused`, 422). An effect that raises must abort its transaction: a key
committed without an outcome is a defect and is reported as one, never replayed.
"""

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.idempotency.errors import (
    IdempotencyKeyReusedError,
    ReadOnlyEffectTransactionError,
    UnfinishedEffectKeyError,
)
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.idempotency.records import KEY_MAX_LENGTH, SCOPE_PATTERN, EffectKeyRecord

SCOPE_NAME: Final = re.compile(SCOPE_PATTERN)
SCOPE_NAME_MAX_LENGTH: Final = 64
# Дольше любого повтора: 24 ч ключа клиента, 5 доставок задачи, 35 дней строк стоимости.
LONGEST_KEEP: Final = timedelta(days=90)
# Ключ может истечь и удалиться между конфликтом и чтением: тогда его захватывают снова.
CLAIM_ATTEMPTS: Final = 2


@dataclass(frozen=True, slots=True)
class EffectScope:
    """A kind of effect: its stable name and how long its keys are kept.

    `keep` must outlast every way the effect can be repeated: the client's retry window for
    an `Idempotency-Key`, the redeliveries of a task, the re-entry of a pipeline stage.
    """

    name: str
    keep: timedelta

    def __post_init__(self) -> None:
        if len(self.name) > SCOPE_NAME_MAX_LENGTH or not SCOPE_NAME.fullmatch(self.name):
            message = "область ключей эффекта — «срез.эффект» в snake_case до 64 символов"
            raise ValueError(message)
        if not timedelta(0) < self.keep <= LONGEST_KEEP:
            message = f"ключи области {self.name} живут больше нуля и не дольше 90 дней"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class EffectKey:
    """One effect: its scope, its key and, for a client's request, the request's print."""

    scope: EffectScope
    key: str
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= len(self.key) <= KEY_MAX_LENGTH:
            message = f"ключ эффекта — от 1 до {KEY_MAX_LENGTH} символов"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Replayable[R]:
    """The outcome of an effect and whether it was stored by an earlier run of the key."""

    outcome: R
    replayed: bool


def fingerprint_of(request: BaseModel) -> str:
    """SHA-256 of the request's canonical JSON: the same request gives the same print."""
    canonical = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def account_key(user_id: UUID, client_key: str) -> str:
    """A client's key bound to its account: two accounts may send the same key."""
    return f"{user_id}:{client_key}"


class EffectLedger:
    """Records effect keys in the caller's transaction; slices receive it by injection."""

    def __init__(self, metrics: EffectKeyMetrics) -> None:
        self._metrics = metrics

    async def once[R: BaseModel](
        self,
        session: AsyncSession,
        effect_key: EffectKey,
        outcome_type: type[R],
        effect: Callable[[], Awaitable[R]],
    ) -> Replayable[R]:
        """Apply the effect unless the key was applied; return the outcome either way."""
        scope, key = effect_key.scope, effect_key.key
        transaction = transaction_info(session)
        if transaction.read_only:
            raise ReadOnlyEffectTransactionError(scope.name)
        fresh = {
            "fingerprint": effect_key.fingerprint,
            "outcome": None,
            "user_id": transaction.scope.user_id,
            "org_id": transaction.scope.org_id,
            "recorded_at": func.now(),
            "expires_at": func.now() + scope.keep,
        }
        statement = insert(EffectKeyRecord).values(scope=scope.name, key=key, **fresh)
        # Живой ключ не трогаем; истёкший занимаем заново, будто его не было.
        claim = statement.on_conflict_do_update(
            index_elements=[EffectKeyRecord.scope, EffectKeyRecord.key],
            set_=fresh,
            where=EffectKeyRecord.expires_at <= func.now(),
        ).returning(EffectKeyRecord.key)
        for _ in range(CLAIM_ATTEMPTS):
            if (await session.execute(claim)).scalar_one_or_none() is not None:
                outcome = await self._apply(session, effect_key, effect)
                return Replayable(outcome, replayed=False)
            stored = await self._stored(session, effect_key, outcome_type)
            if stored is not None:
                return Replayable(stored, replayed=True)
        raise UnfinishedEffectKeyError(scope.name)

    async def _apply[R: BaseModel](
        self, session: AsyncSession, effect_key: EffectKey, effect: Callable[[], Awaitable[R]]
    ) -> R:
        outcome = await effect()
        await session.execute(
            update(EffectKeyRecord)
            .where(
                EffectKeyRecord.scope == effect_key.scope.name,
                EffectKeyRecord.key == effect_key.key,
            )
            .values(outcome=outcome.model_dump(mode="json"))
        )
        return outcome

    async def _stored[R: BaseModel](
        self, session: AsyncSession, effect_key: EffectKey, outcome_type: type[R]
    ) -> R | None:
        """The outcome stored under the key; None when the key was purged meanwhile."""
        row = (
            await session.execute(
                select(EffectKeyRecord.fingerprint, EffectKeyRecord.outcome).where(
                    EffectKeyRecord.scope == effect_key.scope.name,
                    EffectKeyRecord.key == effect_key.key,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        scope = effect_key.scope.name
        if row.fingerprint != effect_key.fingerprint:
            self._metrics.count_repeat(scope, "reused")
            raise IdempotencyKeyReusedError
        if row.outcome is None:
            raise UnfinishedEffectKeyError(scope)
        self._metrics.count_repeat(scope, "replayed")
        return outcome_type.model_validate(row.outcome)
