"""Threshold revisions and the states of policy versions, as the operator changes them (DL-D6).

A calibration adds a revision — passing or not, with its report. A promotion puts a version
with one of its revisions in shadow or active; the version that held that state before is
retired in the same transaction, and the database's unique indexes keep one per point. The
shadow's decisions are counted in both homes as the sweep role, read only: they hold no
person's id, and the window before activation is counted in them.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.infrastructure.records import (
    DecisionRow,
    PolicyStateRow,
    ThresholdRevisionRow,
)

EU = TenancyScope(Home.EU)
POLICY = PolicyStateRow
REVISION = ThresholdRevisionRow


@dataclass(frozen=True, slots=True)
class StoredRevision:
    """A fitted revision of a version."""

    point: str
    version: int
    revision: int
    digest: str
    passed: bool
    report: Mapping[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class VersionState:
    """A version's state and the revision it uses."""

    point: str
    version: int
    state: str
    revision: int
    changed_at: datetime


class PolicyAdmin:
    """Revisions and version states in the EU home; shadow counts in both homes."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    async def add_revision(
        self,
        point: str,
        version: int,
        digest: str,
        fitted: tuple[Mapping[str, Any], Mapping[str, Any], bool],
    ) -> int:
        """Store a fitted revision with its report; its number, the next of the version."""
        cuts, report, passed = fitted
        async with self._transactions.begin(EU) as session:
            last = await session.scalar(
                select(func.max(REVISION.revision)).where(
                    REVISION.point == point, REVISION.version == version
                )
            )
            number = (last or 0) + 1
            await session.execute(
                insert(REVISION).values(
                    point=point, version=version, revision=number, questions_digest=digest,
                    cuts=dict(cuts), report=dict(report), passed=passed,
                )
            )  # fmt: skip
        return number

    async def revision(self, point: str, version: int, number: int) -> StoredRevision | None:
        """One revision, or None."""
        async with self._transactions.begin(EU, read_only=True) as session:
            row = await session.get(REVISION, (point, version, number))
        if row is None:
            return None
        return StoredRevision(
            row.point, row.version, row.revision, row.questions_digest, row.passed,
            dict(row.report), row.created_at,
        )  # fmt: skip

    async def revisions(self, point: str) -> Sequence[StoredRevision]:
        """Every revision of a point's versions, newest first."""
        async with self._transactions.begin(EU, read_only=True) as session:
            rows = await session.scalars(
                select(REVISION).where(REVISION.point == point).order_by(REVISION.created_at.desc())
            )
            return [
                StoredRevision(
                    r.point, r.version, r.revision, r.questions_digest, r.passed, dict(r.report),
                    r.created_at,
                )
                for r in rows
            ]  # fmt: skip

    async def states(self, point: str) -> Sequence[VersionState]:
        """Every version of a point that was ever in force."""
        async with self._transactions.begin(EU, read_only=True) as session:
            rows = await session.scalars(
                select(POLICY).where(POLICY.point == point).order_by(POLICY.version)
            )
            return [
                VersionState(r.point, r.version, r.state, r.revision, r.changed_at) for r in rows
            ]

    async def set_state(
        self, target: tuple[str, int, int, str], digest: str, note: str | None
    ) -> None:
        """Put a version with a revision in a state, retiring the version that held it."""
        point, version, revision, state = target
        async with self._transactions.begin(EU) as session:
            if state in {"active", "shadow"}:
                await session.execute(
                    update(POLICY)
                    .where(POLICY.point == point, POLICY.state == state, POLICY.version != version)
                    .values(state="retired", changed_at=func.now())
                )
            statement = insert(POLICY).values(
                point=point, version=version, state=state, revision=revision,
                questions_digest=digest, note=note,
            )  # fmt: skip
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[POLICY.point, POLICY.version],
                    set_={"state": state, "revision": revision, "questions_digest": digest,
                          "note": note, "changed_at": func.now()},
                )
            )  # fmt: skip

    async def shadow_decisions(self, point: str, version: int, since: datetime) -> int:
        """The shadow's decisions of a version since a moment, in both homes."""
        query = (
            select(func.count())
            .select_from(DecisionRow)
            .where(
                DecisionRow.point == point,
                DecisionRow.version == version,
                DecisionRow.shadow.is_(True),
                DecisionRow.created_at >= since,
            )
        )
        total = 0
        for home in Home:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                total += int(await session.scalar(query) or 0)
        return total
