"""Re-encrypting a home's secrets under the active Fernet key, and counting the lost ones.

While `FERNET_KEYS_PREVIOUS` holds an old key, the weekly job re-encrypts every secret of the
home under the active key, each in its owner's scope; once a full pass is done the runbook
removes the old key. Without an old key the job only checks that every secret still opens.
Either way it sets `shosai_connectors_undecryptable_secrets` for the home, which must stay 0.
"""

from collections.abc import Sequence
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select, update

from shosai.core.crypto.key_ring import FernetKeyRing, UndecryptableCiphertextError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.store.records import GrantSecretRecord

PAGE: Final = 500
log = structlog.stdlib.get_logger(__name__)
COLUMNS: Final = ("access_token_enc", "refresh_token_enc", "secret_enc")


class KeyRotation:
    """The weekly pass over a home's secrets."""

    def __init__(
        self,
        transactions: HomeTransactions,
        keys: FernetKeyRing | None,
        *,
        rotating: bool,
        metrics: ConnectorsMetrics,
    ) -> None:
        self._transactions = transactions
        self._keys = keys
        self._rotating = rotating
        self._metrics = metrics

    async def run(self, home: Home) -> None:
        """Re-encrypt or check every secret of the home; set the lost ones' gauge."""
        if self._keys is None:
            return
        lost, last = 0, None
        while True:
            page = await self._page(home, last)
            for grant_id, user_id, org_id in page:
                lost += await self._one(TenancyScope(home, user_id, org_id), grant_id)
            if len(page) < PAGE:
                break
            last = page[-1][0]
        self._metrics.undecryptable(home, lost)
        log.info("Секреты дома проверены", home=home.value, rotated=self._rotating, lost=lost)

    async def _page(
        self, home: Home, after: UUID | None
    ) -> Sequence[tuple[UUID, UUID, UUID | None]]:
        secrets = GrantSecretRecord
        query = select(secrets.grant_id, secrets.user_id, secrets.org_id).order_by(secrets.grant_id)
        if after is not None:
            query = query.where(secrets.grant_id > after)
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            rows = (await s.execute(query.limit(PAGE))).all()
        return [(row[0], row[1], row[2]) for row in rows]

    async def _one(self, scope: TenancyScope, grant_id: UUID) -> int:
        keys = self._keys
        if keys is None:
            return 0
        query = select(
            GrantSecretRecord.access_token_enc, GrantSecretRecord.refresh_token_enc,
            GrantSecretRecord.secret_enc,
        ).where(GrantSecretRecord.grant_id == grant_id)  # fmt: skip
        async with self._transactions.begin(scope, read_only=not self._rotating) as session:
            row = (
                await session.execute(query.with_for_update() if self._rotating else query)
            ).first()
            if row is None:
                return 0
            renewed: dict[str, bytes] = {}
            try:
                for name, value in zip(COLUMNS, row, strict=True):
                    if value is not None:
                        renewed[name] = keys.rotate(value) if self._rotating else value
                        keys.decrypt(renewed[name])
            except UndecryptableCiphertextError:
                log.error("Секрет гранта не расшифровывается ни одним ключом кольца")
                return 1
            if self._rotating and renewed:
                await session.execute(
                    update(GrantSecretRecord)
                    .where(GrantSecretRecord.grant_id == grant_id)
                    .values(renewed)
                )
        return 0
