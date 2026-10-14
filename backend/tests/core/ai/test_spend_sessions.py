"""A live session reserves its minutes ahead and stops at its ceiling (§3.6)."""

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, SpendLimit, SpendPeriod
from shosai.core.ai.errors import AiFailure
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.results import LiveEnd, LiveEvent, LiveToolCall, LiveUsage, Unit, Usage
from shosai.core.ai.sessions.live import LiveSessions
from tests.core.ai.bench import OPEN_CEILINGS, ai_bench
from tests.core.ai.test_spend import CHEAP, call, guard_over
from tests.harness.database_access import DatabaseAccess


class SilentSession:
    """A live connection that answers nothing until it is closed."""

    def __init__(self) -> None:
        self.closed = asyncio.Event()

    @property
    def input_rate(self) -> int:
        """PCM16 at 16 kHz."""
        return 16_000

    async def send_audio(self, pcm: bytes) -> None:
        """Take the audio."""

    async def end_turn(self) -> None:
        """Nothing to commit."""

    async def send_tool_result(self, call: LiveToolCall, result: str) -> None:
        """No tools."""

    async def events(self) -> AsyncIterator[LiveEvent | LiveUsage]:
        """Nothing, then the end."""
        await self.closed.wait()
        yield LiveEnd(None)

    def floor(self, seconds: float) -> Usage:
        """Billed by the second."""
        return Usage(units=Decimal(str(round(seconds, 3))), unit=Unit.AUDIO_SECOND)

    async def close(self) -> None:
        """Close."""
        self.closed.set()


async def test_a_session_that_reaches_its_ceiling_is_stopped_with_that_code(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = ai_bench(homes.transactions)
    # Минута стоит 6000 мкр$; потолок пускает первую минуту и не пускает вторую сверху.
    context = call(CallClass.STANDARD, limits=(SpendLimit(SpendPeriod.HOUR, 9000),))
    live = MeteredCall(context, CHEAP, "live_transcription", {Unit.AUDIO_SECOND: Decimal("0.0001")})
    sessions = LiveSessions(bench.minutes, guard_over(valkey, OPEN_CEILINGS), renew_every=0.1)
    silent = SilentSession()

    async def opened() -> SilentSession:
        return silent

    async with sessions.run(live, opened) as session:
        events = [event async for event in session.events()]

    assert events == [LiveEnd(AiFailure.SPEND_LIMIT)]
