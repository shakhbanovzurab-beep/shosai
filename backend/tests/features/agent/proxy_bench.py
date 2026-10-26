"""The native proxy's routes over the turn bench (agent step 14): the people, terms, profiles
and homes of the turn bench, a scripted provider stream, and the shipped clients' bodies."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Final

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.ai.calls import CallContext, ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta, Usage
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.features.agent.application.native_proxy import NativeProxy
from shosai.features.agent.channels.http.native_proxy import build_native_proxy_router
from shosai.features.agent.infrastructure.proxy_metrics import ProxyMetrics
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.agent.turn_bench import ROUTE, TurnBench
from tests.features.agent.turn_doubles import Profiles

CHAT: Final = "/v1/ai/chat/stream"
VISION: Final = "/v1/ai/vision/analyze"
MODEL: Final = ModelRef(Provider.OPENROUTER, "probe/answering")
PNG: Final = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
# Тело macOS: пустое системное сообщение первым, без temperature и max_tokens.
MACOS: Final = {
    "role": "responses",
    "messages": [
        {"role": "system", "content": ""},
        {"role": "user", "content": "What did they offer?"},
    ],
    "use_kb": False,
}
# Тело Windows: null в необязательных полях, без системного сообщения.
WINDOWS: Final = {
    "role": "responses", "messages": [{"role": "user", "content": "Цена?"}],
    "temperature": None, "max_tokens": None, "use_kb": True, "client_hint": "kept",
}  # fmt: skip


@dataclass
class ProxyModel:
    """The provider port's stream: its pieces, a failure, a gate after the first piece."""

    pieces: list[ChatDelta] = field(default_factory=list)
    failure: AiCallError | None = None
    fail_at_once: bool = False
    gate: asyncio.Event = field(default_factory=asyncio.Event)
    calls: list[ChatRequest] = field(default_factory=list)
    drained: bool = False

    def __post_init__(self) -> None:
        self.gate.set()

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        del context, route
        self.calls.append(request)
        if self.fail_at_once and self.failure is not None:
            raise self.failure
        for index, piece in enumerate(self.pieces):
            if index > 0:
                await self.gate.wait()
            yield piece
        if self.failure is not None:
            raise self.failure
        self.drained = True


def profiles_of(bench: ProxyBench) -> Profiles:
    """The bench's profiles, to set a person's language."""
    profiles = bench.turns.ports.get(ACCOUNT_PROFILE_READER)
    assert isinstance(profiles, Profiles)
    return profiles


def spoken(*texts: str) -> list[ChatDelta]:
    """A model's answer in pieces, its finish and then its usage."""
    used = Usage(input_tokens=9, output_tokens=2, reported_cost_usd=Decimal("0.0001"))
    return [
        *(ChatDelta(text=text, model=MODEL) for text in texts),
        ChatDelta(finish_reason="stop", model=MODEL),
        ChatDelta(usage=used, model=MODEL),
    ]


@dataclass(frozen=True, slots=True)
class ProxyBench:
    """The proxy's routes over the turn bench's people, terms and homes."""

    http: httpx.AsyncClient
    proxy: NativeProxy
    model: ProxyModel
    turns: TurnBench


@pytest_asyncio.fixture
async def proxy_bench(turn_bench: TurnBench) -> AsyncIterator[ProxyBench]:
    """The two routes with a scripted provider stream."""
    registry = CollectorRegistry()
    model = ProxyModel(pieces=spoken("Hel", "lo there"))
    limiter = RateLimiter(turn_bench.valkey, KeyValueMetrics(registry))
    limit = RateLimit("agent.proxy_bench", 3, timedelta(minutes=1), 3)
    proxy = NativeProxy(
        (turn_bench.homes.transactions, turn_bench.ports, model, limiter),
        lambda: ROUTE, ProxyMetrics(registry), limit,
    )  # fmt: skip
    app = build_probe_app(extra=(build_native_proxy_router(proxy, turn_bench.ports),)).app
    async with client_of(app) as http:
        yield ProxyBench(http, proxy, model, turn_bench)
