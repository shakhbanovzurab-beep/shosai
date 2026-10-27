"""Records and outcomes written in batches, off every caller's path (DL-D7, ADR 0069).

A decision never waits for its record: rows are buffered in the process, per home and table,
and written with one statement every second, or as soon as 500 wait, and once more when the
process stops. Records are telemetry: a home that refuses a batch loses it — logged and
counted — and a buffer past its cap drops new rows the same way, so a slow database never
grows the process's memory. The application may only insert into these tables, so a batch
is a plain multi-row insert, never one that reads back.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Final, Self

import structlog
from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.model_base import ModelBase
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.infrastructure.metrics import DecisionMetrics
from shosai.features.decisions.infrastructure.records import DecisionOutcomeRow, DecisionRow

EVERY: Final = timedelta(seconds=1)
BATCH: Final = 500
CAP: Final = 10_000
TABLES: Final[tuple[type[ModelBase], ...]] = (DecisionRow, DecisionOutcomeRow)
log = structlog.stdlib.get_logger(__name__)

type Row = dict[str, Any]


class RecordWriter:
    """Buffers rows per home and table and writes them in batches."""

    def __init__(
        self,
        transactions: HomeTransactions,
        metrics: DecisionMetrics,
        *,
        every: timedelta = EVERY,
        batch: int = BATCH,
        cap: int = CAP,
    ) -> None:
        self._transactions = transactions
        self._metrics = metrics
        self._every = every.total_seconds()
        self._batch = batch
        self._cap = cap
        self._buffers: dict[tuple[Home, type[ModelBase]], list[Row]] = {}
        self._full = asyncio.Event()
        self._stopping = False

    def add_decision(self, home: Home, row: Row) -> None:
        """Buffer a decision's record."""
        self._add(home, DecisionRow, row)

    def add_outcome(self, home: Home, row: Row) -> None:
        """Buffer what followed a decided subject."""
        self._add(home, DecisionOutcomeRow, row)

    def _add(self, home: Home, table: type[ModelBase], row: Row) -> None:
        buffer = self._buffers.setdefault((home, table), [])
        if len(buffer) >= self._cap:
            self._metrics.lost(table.__tablename__, 1)
            return
        buffer.append(row)
        if len(buffer) >= self._batch:
            self._full.set()

    def pending(self) -> int:
        """Rows waiting to be written."""
        return sum(len(rows) for rows in self._buffers.values())

    async def flush(self) -> None:
        """Write every buffered row, one statement per home and table."""
        self._full.clear()
        for key in list(self._buffers):
            rows = self._buffers.pop(key, [])
            if rows:
                await self._write(*key, rows)

    async def _write(self, home: Home, table: type[ModelBase], rows: list[Row]) -> None:
        try:
            async with self._transactions.begin(TenancyScope(home)) as session:
                await session.execute(insert(table), rows)
        except (SQLAlchemyError, HomeUnavailableError) as error:
            self._metrics.lost(table.__tablename__, len(rows))
            log.error(
                "Записи решений не сохранены",
                home=home.value,
                table=table.__tablename__,
                rows=len(rows),
                error=type(error).__name__,
            )

    @asynccontextmanager
    async def running(self) -> AsyncIterator[Self]:
        """Write in the background while open; on close, finish the batch being written and
        write what is left — a write is never cut in the middle."""
        self._stopping = False
        loop = asyncio.create_task(self._loop(), name="decisions.records")
        try:
            yield self
        finally:
            self._stopping = True
            self._full.set()
            await loop
            await self.flush()

    async def _loop(self) -> None:
        while not self._stopping:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._full.wait(), timeout=self._every)
            await self.flush()
