"""Core's handler of a person's data: mail, unsubscriptions, AI costs (ADR 0045 point 7).

Export gives the mail without its encrypted secrets, the unsubscriptions and the cost rows
of the person's AI calls. Erasure deletes every mail row of the account, whatever its
status, and the unsubscriptions; cost rows are kept by law, and core's other tables expire
on their own (`CORE_ACCOUNT_DATA`).
"""

from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy import delete

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import CORE_ACCOUNT_DATA
from shosai.core.ai.costs.records import ProviderCost
from shosai.core.db.person_rows import PersonRows, person_lines
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.records import EmailMessage, EmailSuppression
from shosai.core.kernel.tenancy import TenancyScope

# Модели импортированы явно: их таблицы есть в метаданных до первого обращения.
TABLES: Final = {
    model.__tablename__: model.metadata.tables[model.__tablename__]
    for model in (EmailMessage, EmailSuppression, ProviderCost)
}
EXPORTED: Final = (
    PersonRows(
        TABLES["email_messages"],
        ("id", "created_at", "recipient", "locale", "kind", "template", "params", "status",
         "finished_at"),
        key="id",
    ),
    PersonRows(TABLES["email_suppressions"], ("kind", "source", "created_at"), key="kind"),
    PersonRows(
        TABLES["provider_costs"],
        ("id", "created_at", "provider", "model", "kind", "feature", "outcome", "input_tokens",
         "output_tokens", "units", "unit", "cost_usd", "cost_rub"),
        key="id",
    ),
)  # fmt: skip


class CoreAccountData:
    """The `core.account_data_handlers` binding of core's own tables."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """Core's declaration."""
        return CORE_ACCOUNT_DATA.owner

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table of core that holds the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the account's mail and unsubscriptions in its home."""
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope) as session:
            await session.execute(
                delete(EmailMessage).where(EmailMessage.user_id == account.user_id)
            )
            await session.execute(
                delete(EmailSuppression).where(EmailSuppression.user_id == account.user_id)
            )
