"""Billing's handler of a person's data: subscription, queue, tombstones, device claims.

Export gives every table (a device claim without its hash), erasure deletes them in the
person's home (ADR 0007: tombstones go with their account), and a transfer copies them
whole and purges the source. Payments, kept by law, arrive with their step.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Final

from sqlalchemy import delete

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.person_rows import (
    PersonRows,
    copy_person_rows,
    person_digest,
    person_lines,
    tables_holding,
    whole_rows,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.infrastructure.minutes_records import (
    FreePlanDeviceRecord,
    UsageEventRecord,
)
from shosai.features.billing.infrastructure.subscription_records import (
    SubscriptionRecord,
    SubscriptionSegmentRecord,
)

OWNER: Final = "billing"
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER,
    (
        TableCoverage("subscriptions", Treatment.ERASE),
        TableCoverage("subscription_segments", Treatment.ERASE),
        TableCoverage("usage_events", Treatment.ERASE),
        TableCoverage("free_plan_devices", Treatment.ERASE),
    ),
)
TABLES: Final = tuple(
    model.metadata.tables[model.__tablename__]
    for model in (
        SubscriptionRecord,
        SubscriptionSegmentRecord,
        UsageEventRecord,
        FreePlanDeviceRecord,
    )
)
MODELS: Final = (
    SubscriptionSegmentRecord,
    SubscriptionRecord,
    UsageEventRecord,
    FreePlanDeviceRecord,
)
ROWS: Final = (
    *(whole_rows(table, key="id") for table in TABLES[:3]),
    whole_rows(TABLES[3], key="device_hash"),
)
EXPORTED: Final = (*ROWS[:3], PersonRows(TABLES[3], ("claimed_at",), key="device_hash"))


class BillingAccountData:
    """The `core.account_data_handlers` binding of billing."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """Billing's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the subscription and its queue in the person's home."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy both tables' rows to the other home."""
        for rows in ROWS:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table in the person's home."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in ROWS
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete both tables' rows in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope) as session:
            for model in MODELS:
                await session.execute(delete(model).where(model.user_id == account.user_id))

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables that still hold the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        return await tables_holding(self._transactions, scope, list(TABLES), account.user_id)
