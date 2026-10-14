"""Core's erasure handler: a deleted person's mail and unsubscriptions (ADR 0045 point 7).

Mail rows hold the address and the text's parameters, so every row of the account goes,
whatever its status; a suppression only names the person. Core's other tables are kept by
law or expire on their own (`CORE_ACCOUNT_DATA`).
"""

from sqlalchemy import delete

from shosai.core.account_data.handlers import AccountRef
from shosai.core.account_data.spec import CORE_ACCOUNT_DATA
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.records import EmailMessage, EmailSuppression
from shosai.core.kernel.tenancy import TenancyScope


class CoreAccountData:
    """The `core.account_data_handlers` binding of core's own tables."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """Core's declaration."""
        return CORE_ACCOUNT_DATA.owner

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
