"""Agent's handler of a person's data: their conversations with Leo and what hangs on them.

The person's rows are their threads with every message, the stored results of tools, the
actions Leo proposed, Settings > Leo, installed skills, ratings and the evaluation cases
they allowed. Runs, the action audit and released pictures' keys hold ids, numbers and
codes only and expire by their partitions or the release tick; pictures are the operator's.
Erasing deletes the threads — messages, ratings and cases go with them by the database's
cascades — and the rest by the person's id, then the in-flight keys of their recent runs and
threads in Valkey; a repeat deletes nothing more. A transfer copies the
conversations, the settings, the skills, the ratings and the cases; tool results and actions
are short-lived and stay behind.
"""

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Final, cast

from redis.asyncio import Redis
from sqlalchemy import Table, delete, select

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.model_base import ModelBase
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
from shosai.features.agent.infrastructure.image_records import (
    AgentImageRecord,
    AgentImageReleaseRecord,
)
from shosai.features.agent.infrastructure.person_records import (
    AgentEvalCaseRecord,
    AgentFeedbackRecord,
    AgentSettingsRecord,
    AgentSkillRecord,
)
from shosai.features.agent.infrastructure.run_keys import (
    lease_key,
    person_runs_key,
    run_keys,
)
from shosai.features.agent.infrastructure.run_records import (
    AgentActionRecord,
    AgentAuditRecord,
    AgentRunRecord,
)
from shosai.features.agent.infrastructure.thread_records import (
    AgentMessageRecord,
    AgentThreadRecord,
    AgentToolResultRecord,
)

OWNER: Final = "agent"
# Ключи Valkey живут не дольше суток: стираются ключи прогонов за это окно.
LIVE_KEYS_WINDOW: Final = timedelta(hours=25)
ERASED: Final[tuple[type[ModelBase], ...]] = (
    AgentThreadRecord,
    AgentMessageRecord,
    AgentToolResultRecord,
    AgentActionRecord,
    AgentSettingsRecord,
    AgentSkillRecord,
    AgentFeedbackRecord,
    AgentEvalCaseRecord,
    # Картинки рисует только оператор: строк человека в них нет, стираются по его id.
    AgentImageRecord,
)
EXPIRING: Final[tuple[type[ModelBase], ...]] = (
    AgentRunRecord,
    AgentAuditRecord,
    AgentImageReleaseRecord,
)
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER,
    tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in ERASED)
    + tuple(TableCoverage(model.__tablename__, Treatment.EXPIRES) for model in EXPIRING),
)
KEYS: Final[Mapping[type[ModelBase], str]] = {
    AgentSettingsRecord: "user_id",
    AgentFeedbackRecord: "message_id",
}
# Переезжают в порядке ссылок: треды раньше сообщений и оценок, оценки раньше случаев.
MOVED: Final[tuple[type[ModelBase], ...]] = (
    AgentThreadRecord,
    AgentMessageRecord,
    AgentFeedbackRecord,
    AgentEvalCaseRecord,
    AgentSettingsRecord,
    AgentSkillRecord,
)


def _rows(model: type[ModelBase]) -> PersonRows:
    return whole_rows(cast("Table", model.__table__), KEYS.get(model, "id"))


EXPORTED: Final = tuple(_rows(model) for model in ERASED)
COPIED: Final = tuple(_rows(model) for model in MOVED)


class AgentAccountData:
    """The `core.account_data_handlers` binding of agent."""

    def __init__(self, transactions: HomeTransactions, valkey: Redis) -> None:
        self._transactions = transactions
        self._valkey = valkey

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table of the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's rows in their home and the in-flight keys of their runs."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy the rows that move with the person to the other home, in reference order."""
        for rows in COPIED:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each moving table's rows of the person in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in COPIED
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's rows in `account.home` and their runs' keys in Valkey."""
        user_id = account.user_id
        since = datetime.now(UTC) - LIVE_KEYS_WINDOW
        async with self._transactions.begin(TenancyScope(account.home, user_id)) as session:
            runs = (
                await session.scalars(
                    select(AgentRunRecord.id).where(
                        AgentRunRecord.user_id == user_id, AgentRunRecord.started_at >= since
                    )
                )
            ).all()
            threads = (
                await session.scalars(
                    select(AgentThreadRecord.id).where(AgentThreadRecord.user_id == user_id)
                )
            ).all()
            # Сообщения, оценки и случаи уходят с тредами каскадом базы.
            await session.execute(
                delete(AgentActionRecord).where(AgentActionRecord.user_id == user_id)
            )
            await session.execute(
                delete(AgentToolResultRecord).where(AgentToolResultRecord.user_id == user_id)
            )
            await session.execute(
                delete(AgentImageRecord).where(AgentImageRecord.user_id == user_id)
            )
            await session.execute(
                delete(AgentThreadRecord).where(AgentThreadRecord.user_id == user_id)
            )
            await session.execute(
                delete(AgentSettingsRecord).where(AgentSettingsRecord.user_id == user_id)
            )
            await session.execute(
                delete(AgentSkillRecord).where(AgentSkillRecord.user_id == user_id)
            )
        keys = [key for run_id in runs for key in run_keys(run_id)]
        keys += [lease_key(thread_id) for thread_id in threads]
        keys.append(person_runs_key(user_id))
        if keys:
            await self._valkey.delete(*keys)

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        tables = [cast("Table", model.__table__) for model in ERASED]
        return await tables_holding(self._transactions, scope, tables, account.user_id)
