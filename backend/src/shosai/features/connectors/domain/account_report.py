"""Atlassian's personal data reporting (plan §3.5): which accounts Shosai holds, and since when.

Shosai keeps an Atlassian account id and its email for each grant. Every cycle — seven days
unless Atlassian names another in `Cycle-Period` — it reports each account with the moment
its profile was read, at most 90 accounts a request; Atlassian answers which accounts were
closed, whose data must be erased, and which changed, whose profile is read again.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

MAX_ACCOUNTS: Final = 90
DEFAULT_CYCLE: Final = timedelta(days=7)


class Verdict(StrEnum):
    """What Atlassian said about one reported account."""

    CLOSED = "closed"
    UPDATED = "updated"


@dataclass(frozen=True, slots=True)
class ReportedAccount:
    """One account and when its personal data was read."""

    account_id: str
    updated_at: datetime


def rfc3339(moment: datetime) -> str:
    """The moment as Atlassian reads it, in UTC with seconds; a naive moment is taken as UTC."""
    aware = moment.astimezone(UTC) if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.isoformat(timespec="seconds").replace("+00:00", "Z")


def cycle_of(header: str | None) -> timedelta | None:
    """The cycle Atlassian named in `Cycle-Period` (seconds); None when it named no usable one."""
    if header is None or not header.strip().isdigit():
        return None
    seconds = int(header.strip())
    return timedelta(seconds=seconds) if seconds > 0 else None


def accounts_of(held: Sequence[ReportedAccount]) -> list[ReportedAccount]:
    """Each account once, with the latest moment its data was read, in a stable order."""
    latest: dict[str, datetime] = {}
    for account in held:
        known = latest.get(account.account_id)
        if known is None or account.updated_at > known:
            latest[account.account_id] = account.updated_at
    return [ReportedAccount(key, latest[key]) for key in sorted(latest)]


def batches(accounts: Sequence[ReportedAccount]) -> list[tuple[ReportedAccount, ...]]:
    """The accounts in requests of at most 90."""
    return [
        tuple(accounts[start : start + MAX_ACCOUNTS])
        for start in range(0, len(accounts), MAX_ACCOUNTS)
    ]
