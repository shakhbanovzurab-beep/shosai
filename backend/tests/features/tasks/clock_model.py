"""The mocks' clocks (`mocks/store/clock-ops.ts`) as a model the API's answers are held to.

One task on one board of columns of known kinds, every request realigning the card as the
mocks' routes do, with the rule settled in plan §3.9: a status changed without a move acts
at the change, on the changer's board.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from shosai.features.tasks.domain.board_fields import StopwatchAutomations
from shosai.features.tasks.domain.clocks import Span, Stopwatch, stopwatch_of


@dataclass
class ClockModel:
    """The task's spans, its card's column and status, and the board's settings."""

    kinds: dict[uuid.UUID, str]
    column: uuid.UUID
    status: str
    automations: StopwatchAutomations | None
    spans: list[Span] = field(default_factory=list)

    def _open(self) -> Span | None:
        return next((span for span in self.spans if span.stopped_at is None), None)

    def start(self, now: datetime) -> None:
        """`startStopwatch`: a span in the card's column unless one runs."""
        if self._open() is None:
            self.spans.append(Span(self.column, now))

    def stop(self, now: datetime) -> bool:
        """`stopOpen`: close the running span; whether one ran."""
        running = self._open()
        if running is None:
            return False
        index = self.spans.index(running)
        self.spans[index] = Span(running.column_id, running.started_at, now)
        return True

    def reset(self) -> None:
        """`resetStopwatch`."""
        self.spans.clear()

    def _follow(self, target: uuid.UUID, now: datetime) -> None:
        """`onDone` then `onMove` from the card's column to another."""
        done = self.status == "done"
        was_running = self.stop(now)
        stops = self.automations is not None and self.automations.stop_on_done
        if done and stops:
            self.column = target
            return
        restarts = self.automations is not None and self.automations.restart_on_move
        self.column = target
        if was_running or (restarts and not done):
            self.start(now)

    def move(self, target: uuid.UUID, now: datetime) -> None:
        """`patchCard` with a column: the column's kind is the status."""
        if target == self.column:
            return
        self.status = self.kinds[target]
        self._follow(target, now)

    def set_status(self, status: str, now: datetime) -> None:
        """`patchTask` with a status, realigned at once on the changer's board: to the first
        column of the status."""
        if status == self.status:
            return
        self.status = status
        target = next(column for column, kind in self.kinds.items() if kind == status)
        self._follow(target, now)

    def stopwatch(self) -> Stopwatch | None:
        """`stopwatchOf`."""
        return stopwatch_of(self.spans)
