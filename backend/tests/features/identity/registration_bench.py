"""Registration over the run's slot: the routes in an HTTP shell, the codes read from mail."""

import json
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

import httpx
from fastapi import APIRouter, FastAPI
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
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
from shosai.core.kv.locks import DistributedLocks
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.core.web.app import HttpTelemetry, build_http_app
from shosai.features.identity.application.authentication import TokenAuthenticator
from shosai.features.identity.application.deletion import Deletions, DeletionWindow
from shosai.features.identity.application.desktop import DesktopSignIn
from shosai.features.identity.application.devices import Devices
from shosai.features.identity.application.exports import Exports
from shosai.features.identity.application.native_me import NativeMe
from shosai.features.identity.application.operators import OperatorRoles, Operators
from shosai.features.identity.application.passwords import Passwords, PasswordServices
from shosai.features.identity.application.profile import Profiles
from shosai.features.identity.application.registration import Registration, RegistrationServices
from shosai.features.identity.application.sessions import Sessions
from shosai.features.identity.application.sign_in import SignIn, SignInServices
from shosai.features.identity.application.social import SocialServices, SocialSignIn
from shosai.features.identity.application.social_accounts import (
    SocialAccounts,
    SocialAccountServices,
)
from shosai.features.identity.application.verification import Verification
from shosai.features.identity.channels.http.admin_operators import build_admin_operators_router
from shosai.features.identity.channels.http.cookies import CookiePolicy
from shosai.features.identity.channels.http.deletion import build_deletion_router
from shosai.features.identity.channels.http.desktop import build_desktop_router
from shosai.features.identity.channels.http.devices import build_devices_router
from shosai.features.identity.channels.http.exports import build_export_router
from shosai.features.identity.channels.http.me import build_me_router
from shosai.features.identity.channels.http.passwords import build_password_router
from shosai.features.identity.channels.http.registration import build_registration_router
from shosai.features.identity.channels.http.sessions import SessionRoutes, build_session_router
from shosai.features.identity.channels.http.social import build_social_router
from shosai.features.identity.channels.http.social_finish import build_social_finish_router
from shosai.features.identity.contracts import AUTHENTICATOR, IDENTITY_EVENTS, OPERATOR_ROLES
from shosai.features.identity.domain.social import Provider
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.captcha import Captcha, CaptchaOff
from shosai.features.identity.infrastructure.consents import ConsentJournal
from shosai.features.identity.infrastructure.desktop_codes import DesktopCodes
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.registration_routes import RegistrationRoutes
from shosai.features.identity.infrastructure.sign_in_failures import SignInFailures
from shosai.features.identity.infrastructure.social.base import SocialProvider
from shosai.features.identity.infrastructure.social.consent_tickets import ConsentTickets
from shosai.features.identity.infrastructure.social.flows import SocialStates
from shosai.features.identity.infrastructure.token_codec import TokenCodec
from shosai.features.identity.settings import TokenKey
from tests.core.email.bench import mail_bench
from tests.features.identity.admin_bench import admin_users_router
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot

DIRECTORY_KEY = b"directory-key-of-the-tests-32-bytes!"
TEST_ROUNDS = 4
SIGNING_KEYS = (TokenKey("k1", SecretStr("signing-key-of-the-identity-tests-32b")),)
COOKIES = CookiePolicy(secure=True, domain=None)
# Пароль формы по умолчанию: проходит правило длины.
SAMPLE_WORDS = "correct horse battery"
# Почтовый сервер тестам не нужен: письма только пишутся в базу и читаются оттуда.
UNUSED_SMTP_PORT = 9


@dataclass(frozen=True, slots=True)
class RegistrationBench:
    """The HTTP client of identity's routes and what tests inspect."""

    http: httpx.AsyncClient
    services: RegistrationServices
    key_ring: FernetKeyRing
    sessions: Sessions
    codec: TokenCodec
    markers: AccountMarkers
    operators: Operators
    app: FastAPI


class EuUnreachable:
    """Transactions whose EU home does not answer; the Russian home works."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    def begin(self, scope: TenancyScope, *, read_only: bool = False) -> object:
        """Refuse the EU home as an outage would."""
        if scope.home is Home.EU:
            raise HomeUnavailableError(Home.EU)
        return self._transactions.begin(scope, read_only=read_only)


@dataclass(frozen=True, slots=True)
class BenchOptions:
    """What a test changes in the bench: an EU outage, a captcha, provider doubles."""

    directory_transactions: Callable[[HomeTransactions], HomeTransactions] | None = None
    captcha: Captcha | None = None
    providers: Mapping[Provider, SocialProvider] = field(default_factory=dict)
    objects: Mapping[Home, ObjectStorage] = field(default_factory=dict)


@asynccontextmanager
async def registration_bench(
    transactions: HomeTransactions,
    valkey: Redis,
    cache: Redis,
    options: BenchOptions | None = None,
) -> AsyncIterator[RegistrationBench]:
    """Identity's routes over the slot, with the captcha off and cheap hashing by default."""
    chosen = options or BenchOptions()
    directory_transactions, captcha = chosen.directory_transactions, chosen.captcha
    registry = CollectorRegistry()
    mail = mail_bench(transactions, UNUSED_SMTP_PORT)
    directory_access = (
        directory_transactions(transactions) if directory_transactions else transactions
    )
    kv_metrics = KeyValueMetrics(registry)
    limiter = RateLimiter(valkey, kv_metrics)
    hasher = PasswordHasher(TEST_ROUNDS, workers=2)
    services = RegistrationServices(
        transactions=transactions,
        directory=Directory(directory_access, RedisCache(cache, CacheMetrics(registry))),
        routes=RegistrationRoutes(valkey),
        hasher=hasher,
        email=mail.port,
        captcha=captcha or CaptchaOff(),
        limiter=limiter,
        directory_key=DIRECTORY_KEY,
    )
    outbox = EventOutbox(EventTypes(list(IDENTITY_EVENTS)))
    codec = TokenCodec(SIGNING_KEYS)
    sessions = Sessions(
        transactions, services.directory, codec,
        SIGNING_KEYS[0].secret.get_secret_value().encode(), DeletionWindow(outbox),
    )  # fmt: skip
    markers = AccountMarkers(valkey)
    ports = PortDirectory()
    ports.install(
        [
            AUTHENTICATOR.bind(TokenAuthenticator(codec, services.directory, markers)),
            OPERATOR_ROLES.bind(OperatorRoles(transactions)),
        ]
    )
    locks = DistributedLocks(valkey, kv_metrics)
    operators = Operators(transactions, services.directory, outbox, locks)
    sign_in = SignIn(
        SignInServices(
            transactions=transactions, directory=services.directory, routes=services.routes,
            hasher=hasher, captcha=captcha or CaptchaOff(), failures=SignInFailures(valkey),
            sessions=sessions, directory_key=DIRECTORY_KEY,
        )
    )  # fmt: skip
    passwords = Passwords(
        PasswordServices(
            transactions=transactions, directory=services.directory, hasher=hasher,
            email=mail.port, captcha=captcha or CaptchaOff(), limiter=limiter, markers=markers,
            outbox=outbox, sessions=sessions, directory_key=DIRECTORY_KEY,
            reset_page="https://shosai.example/app/reset",
        )
    )  # fmt: skip
    profiles = Profiles(transactions, ConsentJournal(), chosen.objects)
    routers = [
        build_me_router(profiles, ports),
        build_registration_router(
            Registration(services), Verification(services, outbox, sessions), limiter, COOKIES
        ),
        build_session_router(
            SessionRoutes(
                sign_in=sign_in, sessions=sessions, me=NativeMe(transactions, ports, profiles),
                ports=ports, limiter=limiter, cookies=COOKIES,
            )
        ),
        build_password_router(passwords, ports, limiter, COOKIES),
        build_desktop_router(
            DesktopSignIn(transactions, DesktopCodes(valkey), sessions), ports, limiter
        ),
        build_devices_router(Devices(transactions, markers, outbox), ports),
        build_export_router(Exports(transactions, chosen.objects), ports, limiter),
        build_admin_operators_router(operators, ports),
        admin_users_router(
            transactions, (services.directory, DIRECTORY_KEY), (markers, outbox), ports
        ),
        build_deletion_router(
            Deletions(transactions, markers, outbox, mail.port), ports, limiter, COOKIES
        ),
        *social_routers_of(transactions, valkey, services.directory, sessions, chosen.providers),
    ]  # fmt: skip
    telemetry = HttpTelemetry(registry, TracerProvider(shutdown_on_exit=False))
    app = build_http_app(WebSettings.model_validate({}), telemetry, routers)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="https://shosai.example"
        ) as http:
            yield RegistrationBench(
                http, services, mail.key_ring, sessions, codec, markers, operators, app
            )
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


def social_routers_of(
    transactions: HomeTransactions,
    valkey: Redis,
    directory: Directory,
    sessions: Sessions,
    providers: Mapping[Provider, SocialProvider],
) -> tuple[APIRouter, ...]:
    """Social sign-in over the slot with the given provider doubles."""
    states = SocialStates(valkey)
    consent = ConsentTickets(SIGNING_KEYS[0].secret.get_secret_value().encode())
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    social = SocialSignIn(
        SocialServices(
            transactions=transactions, directory=directory, states=states, consent=consent,
            providers=dict(providers), state_key=b"social-state-key-of-the-tests-32b",
            directory_key=DIRECTORY_KEY, base_url="https://shosai.example",
        )
    )  # fmt: skip
    accounts = SocialAccounts(
        SocialAccountServices(
            transactions=transactions, directory=directory, states=states, consent=consent,
            sessions=sessions, outbox=EventOutbox(EventTypes(list(IDENTITY_EVENTS))),
            directory_key=DIRECTORY_KEY,
        )
    )  # fmt: skip
    widget_ids = {Provider.YANDEX: "yandex-client", Provider.GOOGLE: "google-client"}
    return (
        build_social_router(social, limiter, widget_ids),
        build_social_finish_router(social, accounts, limiter, COOKIES),
    )
