"""Many effects of one scope, each applied once, in one transaction (F6-C5).

`EffectLedger.once` serves one effect per transaction. A batch — the minute rows of every
live session of a home — claims all its keys with one multi-row insert: a key already live
is a repeat and its effect is skipped; an expired one is taken over as new. The caller
applies the effects of the claimed keys and records their outcomes in the same
transaction, so keys, effects and outcomes still commit together.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Text, column, func, update, values
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.idempotency.errors import ReadOnlyEffectTransactionError
from shosai.core.idempotency.ledger import EffectScope
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.idempotency.records import EffectKeyRecord


@dataclass(frozen=True, slots=True)
class BatchKey:
    """One key of a batch and the account and company its effect belongs to."""

    key: str
    user_id: UUID | None = None
    org_id: UUID | None = None


class EffectBatch:
    """Claims and completes the keys of a batch in the caller's transaction."""

    def __init__(self, metrics: EffectKeyMetrics) -> None:
        self._metrics = metrics

    async def claim(
        self, session: AsyncSession, scope: EffectScope, keys: Sequence[BatchKey]
    ) -> frozenset[str]:
        """The keys whose effects this transaction must apply; the rest are repeats."""
        if transaction_info(session).read_only:
            raise ReadOnlyEffectTransactionError(scope.name)
        unique = {item.key: item for item in keys}
        if not unique:
            return frozenset()
        statement = insert(EffectKeyRecord).values(
            [
                {"scope": scope.name, "key": item.key, "fingerprint": None, "outcome": None,
                 "user_id": item.user_id, "org_id": item.org_id, "recorded_at": func.now(),
                 "expires_at": func.now() + scope.keep}
                for item in unique.values()
            ]
        )  # fmt: skip
        excluded = statement.excluded
        # Живой ключ не трогаем; истёкший занимаем заново, будто его не было.
        claim = statement.on_conflict_do_update(
            index_elements=[EffectKeyRecord.scope, EffectKeyRecord.key],
            set_={
                "fingerprint": None,
                "outcome": None,
                "user_id": excluded.user_id,
                "org_id": excluded.org_id,
                "recorded_at": func.now(),
                "expires_at": excluded.expires_at,
            },
            where=EffectKeyRecord.expires_at <= func.now(),
        ).returning(EffectKeyRecord.key)
        claimed = frozenset((await session.execute(claim)).scalars().all())
        for _ in range(len(unique) - len(claimed)):
            self._metrics.count_repeat(scope.name, "replayed")
        return claimed

    async def complete(
        self, session: AsyncSession, scope: EffectScope, outcomes: Mapping[str, BaseModel]
    ) -> None:
        """Store the outcome of each claimed key, in one statement."""
        if not outcomes:
            return
        done = values(column("key", Text), column("outcome", JSONB), name="done").data(
            [(key, outcome.model_dump(mode="json")) for key, outcome in outcomes.items()]
        )
        await session.execute(
            update(EffectKeyRecord)
            .where(EffectKeyRecord.scope == scope.name, EffectKeyRecord.key == done.c.key)
            .values(outcome=done.c.outcome)
        )
