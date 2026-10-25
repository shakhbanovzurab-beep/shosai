"""The model's answer as it is written, into the run's stream (Leo §4.3, §13.2).

A separate task reads the provider's stream, so waiting never cancels it; the run takes the
pieces and writes them to its log at most every 100 ms — a 180 s turn stays well inside the
log's 2 000 events, and a reader sees text within a tenth of a second. A model silent for
45 s ends the run `model_unavailable`; the time to the first piece of text is measured. The
buffer outlives a round: the person reads one answer, so the text a later round writes after
earlier text is set apart by a blank line, in the stream as in the kept answer.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from shosai.core.ai.requests import ToolCall
from shosai.core.ai.results import ChatDelta, Usage
from shosai.features.agent.domain.runs import STREAM_STALL
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer

FLUSH: Final = timedelta(milliseconds=100)
ROUND_BREAK: Final = "\n\n"


class ModelStalledError(Exception):
    """The model wrote nothing for longer than the stall limit."""


class AnswerBuffer:
    """The text so far, the part not yet written to the log, and the round's last facts."""

    def __init__(self, write: Callable[[str], Awaitable[None]], started: float) -> None:
        self.parts: list[str] = []
        self.finish_reason: str | None = None
        self.usage: Usage | None = None
        self.first_token_ms: int | None = None
        self.model: str | None = None
        self.tool_calls: tuple[ToolCall, ...] = ()
        self._write = write
        self._pending: list[str] = []
        self._started = started
        self._round_start = 0
        self.flushed_at = started

    def restore(self, text: str) -> None:
        """Go on after the answer a resumed run wrote before its card; it is in the log."""
        self.parts = [text] if text else []
        self._round_start = len(self.parts)

    def begin_round(self) -> None:
        """Start a model call: its facts are its own, its text follows the earlier text."""
        self.finish_reason, self.usage, self.tool_calls = None, None, ()
        self._round_start = len(self.parts)

    @property
    def text(self) -> str:
        """Everything the model wrote."""
        return "".join(self.parts)

    @property
    def pending(self) -> bool:
        """Whether some text waits to be written."""
        return bool(self._pending)

    def take(self, delta: ChatDelta, now: float) -> None:
        """Keep one piece of the stream."""
        if delta.text:
            if self.first_token_ms is None:
                self.first_token_ms = int((now - self._started) * 1000)
            text = delta.text
            if len(self.parts) == self._round_start and self.parts:
                text = ROUND_BREAK + text.lstrip("\n")
            self.parts.append(text)
            self._pending.append(text)
        self.finish_reason = delta.finish_reason or self.finish_reason
        self.usage = delta.usage or self.usage
        self.tool_calls = delta.tool_calls or self.tool_calls
        if delta.model is not None:
            self.model = delta.model.model

    async def flush(self, now: float) -> None:
        """Write the waiting text as one event."""
        if self._pending:
            text, self._pending = "".join(self._pending), []
            await self._write(text)
        self.flushed_at = now

    def answer(self) -> ModelAnswer:
        """The round's answer as the model left it: its own text and its calls."""
        text = "".join(self.parts[self._round_start :]).removeprefix(ROUND_BREAK)
        return ModelAnswer(
            text, self.finish_reason, self.usage, self.first_token_ms, self.model, self.tool_calls
        )


@dataclass(frozen=True, slots=True)
class Pace:
    """How often waiting text is written, and how long the model may stay silent."""

    flush: timedelta = FLUSH
    stall: timedelta = STREAM_STALL


DEFAULT_PACE: Final = Pace()


async def stream_answer(
    deltas: AsyncIterator[ChatDelta],
    kept: AnswerBuffer,
    pace: Pace = DEFAULT_PACE,
    clock: Callable[[], float] = time.monotonic,
) -> ModelAnswer:
    """Read the model's stream to its end, writing text as it comes; the buffer keeps the
    text so far for a run stopped midway."""
    queue: asyncio.Queue[ChatDelta] = asyncio.Queue()

    async def produce() -> None:
        async for delta in deltas:
            queue.put_nowait(delta)

    producer = asyncio.create_task(produce(), name="agent-model-stream")
    last_piece = clock()
    try:
        while True:
            due = kept.flushed_at + pace.flush.total_seconds() if kept.pending else None
            limit = last_piece + pace.stall.total_seconds()
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait(
                {getter, producer},
                timeout=max(0.0, min(due or limit, limit) - clock()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if getter in done:
                last_piece = clock()
                kept.take(getter.result(), last_piece)
                if kept.pending and last_piece - kept.flushed_at >= pace.flush.total_seconds():
                    await kept.flush(last_piece)
                continue
            getter.cancel()
            if producer in done:
                if queue.empty():
                    producer.result()
                    break
                continue
            if kept.pending:
                await kept.flush(clock())
                continue
            raise ModelStalledError
        await kept.flush(clock())
    finally:
        if not producer.done():
            producer.cancel()
        # Ошибку чтения уже подняли выше через result(); здесь задача только дожидается конца.
        await asyncio.gather(producer, return_exceptions=True)
    return kept.answer()
