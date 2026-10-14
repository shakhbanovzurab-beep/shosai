"""Registration over the run's slot: the routes in an HTTP shell, the codes read from mail."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast
from uuid import UUID

import httpx
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.cache.metrics import CacheMetrics
from shosai.core.cache.redis_cache import RedisCache
from shosai.core.config.sections import WebSettings
from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.web.app import HttpTelemetry, build_http_app
from shosai.features.identity.application.registration import Registration, RegistrationServices
from shosai.features.identity.application.verification import Verification
from shosai.features.identity.channels.http.registration import build_registration_router
from shosai.features.identity.contracts import IDENTITY_EVENTS
from shosai.features.identity.infrastructure.captcha import CaptchaOff
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.registration_routes import RegistrationRoutes
from tests.core.email.bench import mail_bench
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot

DIRECTORY_KEY = b"directory-key-of-the-tests-32-bytes!"
TEST_ROUNDS = 4
# Пароль формы по умолчанию: проходит правило длины.
SAMPLE_WORDS = "correct horse battery"
# Почтовый сервер тестам не нужен: письма только пишутся в базу и читаются оттуда.
UNUSED_SMTP_PORT = 9


@dataclass(frozen=True, slots=True)
class RegistrationBench:
    """The HTTP client of the registration routes and what tests inspect."""

    http: httpx.AsyncClient
    services: RegistrationServices
    key_ring: FernetKeyRing


class EuUnreachable:
    """Transactions whose EU home does not answer; the Russian home works."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    def begin(self, scope: TenancyScope, *, read_only: bool = False) -> object:
        """Refuse the EU home as an outage would."""
        if scope.home is Home.EU:
            raise HomeUnavailableError(Home.EU)
        return self._transactions.begin(scope, read_only=read_only)


@asynccontextmanager
async def registration_bench(
    transactions: HomeTransactions,
    valkey: Redis,
    cache: Redis,
    directory_transactions: Callable[[HomeTransactions], HomeTransactions] | None = None,
) -> AsyncIterator[RegistrationBench]:
    """The registration routes over the slot, with the captcha off and cheap hashing."""
    registry = CollectorRegistry()
    mail = mail_bench(transactions, UNUSED_SMTP_PORT)
    directory_access = (
        directory_transactions(transactions) if directory_transactions else transactions
    )
    limiter = RateLimiter(valkey, KeyValueMetrics(registry))
    hasher = PasswordHasher(TEST_ROUNDS, workers=2)
    services = RegistrationServices(
        transactions=transactions,
        directory=Directory(directory_access, RedisCache(cache, CacheMetrics(registry))),
        routes=RegistrationRoutes(valkey),
        hasher=hasher,
        email=mail.port,
        captcha=CaptchaOff(),
        limiter=limiter,
        directory_key=DIRECTORY_KEY,
    )
    outbox = EventOutbox(EventTypes(list(IDENTITY_EVENTS)))
    router = build_registration_router(
        Registration(services), Verification(services, outbox), limiter
    )
    telemetry = HttpTelemetry(registry, TracerProvider(shutdown_on_exit=False))
    app = build_http_app(WebSettings.model_validate({}), telemetry, [router])
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="https://shosai.example"
        ) as http:
            yield RegistrationBench(http, services, mail.key_ring)
    finally:
        hasher.close()


def eu_unreachable(transactions: HomeTransactions) -> HomeTransactions:
    """The directory's transactions with the EU home out of reach."""
    return cast("HomeTransactions", EuUnreachable(transactions))


async def mailed_codes(run_slot: RunSlot, key_ring: FernetKeyRing, home: Home) -> list[str]:
    """The registration codes mailed from a home, oldest first."""
    rows = await fetch_rows(
        run_slot.claimed.connections[home],
        "SELECT secrets FROM email_messages WHERE template = 'identity.registration_code' "
        "ORDER BY created_at, id",
    )
    return [json.loads(key_ring.decrypt(row["secrets"]))["code"] for row in rows]


def form(email: str, country: str = "RU", password: str | None = None) -> dict[str, object]:
    """A registration form that passes every rule."""
    return {
        "email": email,
        "password": password or SAMPLE_WORDS,
        "full_name": "Anna Petrova",
        "country": country,
        "language": "ru",
        "consents": {"personal_data": True, "cross_border": True, "marketing": False},
    }


async def register(http: httpx.AsyncClient, body: dict[str, object]) -> UUID:
    """Start a registration and return its id."""
    response = await http.post("/v1/auth/register", json=body)
    assert response.status_code == 202, response.text
    return UUID(response.json()["registration_id"])
