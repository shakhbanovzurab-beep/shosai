"""The voice route end to end: a real uvicorn on the WS gateway, Gemini on the local live
server, the agent over the turn bench, the plan's minutes as a double (LEO-voice step 5)."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

import pytest_asyncio
from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.typing import Origin

from shosai.core.ai.adapters.gemini_live import GeminiLive, gemini_client
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.kernel.homes import Home
from shosai.core.kv.locks import DistributedLocks
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.ports.directory import PortDirectory
from shosai.core.runtime.servers import HttpServer, server_config
from shosai.core.web.sockets import SocketGateway, SocketMetrics
from shosai.features.agent.contracts.voice import VOICE_TURNS
from shosai.features.billing.contracts import MINUTES_ALLOWANCE, MinutesExhaustedError
from shosai.features.billing.domain.meters import MinutesLeft
from shosai.features.capture.application.voice_minutes import VoiceMinutesCount
from shosai.features.capture.channels.voice_session import ROUTE, VoiceParts, VoiceSessions
from shosai.features.capture.channels.ws import build_voice_router
from shosai.features.capture.infrastructure.voice_metrics import VoiceMetrics
from shosai.features.identity.contracts import AUTHENTICATOR
from tests.core.ai.bench import Doubles, ai_bench, set_prices
from tests.doubles.live_server import LiveServer, client_tls, live_server
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.turn_bench import TurnBench
from tests.features.agent.voice_doubles import agent_voices
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.capture.voice_scenario import budget_question
from tests.harness.process_environ import LOOPBACK, loopback_socket

CABINET: Final = Origin("https://shosai.example")
VOICE: Final = ModelRef(Provider.GOOGLE, "gemini-3.8-live")
EVER: Final = (datetime(2000, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC))


@dataclass
class Allowance:
    """The plan's monthly minutes, counted from the voice conversations' rows."""

    limit_minutes: int | None = 60

    async def check(
        self, session: AsyncSession, user_id: uuid.UUID, device: str | None
    ) -> MinutesLeft:
        """Minutes left; refused when used up."""
        del device
        left = MinutesLeft(
            self.limit_minutes, await VoiceMinutesCount().recorded_seconds(session, user_id, EVER)
        )
        if left.exhausted and self.limit_minutes is not None:
            raise MinutesExhaustedError(self.limit_minutes)
        return left

    async def covers(self, session: AsyncSession, user_id: uuid.UUID, seconds: int) -> MinutesLeft:
        """Uploads have no part here: the check alone."""
        del seconds
        return await self.check(session, user_id, None)


@dataclass(frozen=True, slots=True)
class VoiceBench:
    """The route's address and what a test inspects around it."""

    url: str
    turn: TurnBench
    allowance: Allowance
    locks: DistributedLocks
    gemini: LiveServer
    registry: CollectorRegistry


def hello(person: uuid.UUID, **fields: object) -> dict[str, object]:
    """The cabinet's first frame for a person of the EU home, in Personal."""
    frame: dict[str, object] = {
        "type": "hello", "v": 1, "token": f"person:{person}:{Home.EU.value}",
        "scope": {"kind": "personal"}, "thread_id": None, "path": "/app", "locale": "en",
    }  # fmt: skip
    return frame | fields


@pytest_asyncio.fixture
async def voice_bench(
    turn_bench: TurnBench, action_bench: ActionBench
) -> AsyncIterator[VoiceBench]:
    """The route over the turn bench, with Gemini playing the budget question."""
    transactions = turn_bench.homes.transactions
    await set_prices(
        transactions, VOICE, input_token="0.00000075", input_audio_token="0.000003",
        output_token="0.0000045", output_audio_token="0.000012",
    )  # fmt: skip
    allowance, registry = Allowance(), CollectorRegistry()
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            VOICE_TURNS.bind(agent_voices(action_bench)),
            MINUTES_ALLOWANCE.bind(allowance),
        ]
    )
    locks = DistributedLocks(turn_bench.valkey, KeyValueMetrics(registry))
    async with live_server(budget_question()) as gemini:
        base_url = gemini.url.replace("wss://", "https://")
        live = GeminiLive(gemini_client("probe-key", base_url, tls=client_tls()))
        ai = ai_bench(transactions, doubles=Doubles(gemini=live, valkey=turn_bench.valkey))
        parts = VoiceParts(transactions, ports, locks, ai.providers, VOICE, VoiceMetrics(registry))
        gateway = SocketGateway(frozenset({str(CABINET)}), 4, SocketMetrics(registry))
        app = FastAPI()
        app.include_router(build_voice_router(gateway, VoiceSessions(parts)))
        config = server_config(
            app, trusted_proxies=None, drain=timedelta(seconds=5), websockets=True
        )
        server = HttpServer("ws-voice", config, LOOPBACK, 0)
        port = await server.start()
        try:
            yield VoiceBench(
                loopback_socket(port, ROUTE), turn_bench, allowance, locks, gemini, registry
            )
        finally:
            await server.stop()
