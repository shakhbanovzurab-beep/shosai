"""The person's billing routes over the entitlement bench, with stand-in sign-in and profiles.

A bearer token `person:<uuid>:<home>` signs that person in; their country comes from the
test's profile map, as identity's profile reader would give it.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from http import HTTPStatus
from uuid import UUID

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.application.people_views import PeopleViews
from shosai.features.billing.application.sales import SalesInquiries
from shosai.features.billing.channels.http.plans import build_plans_router
from shosai.features.billing.channels.http.usage import build_usage_router
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    AUTHENTICATOR,
    AccountProfile,
    Principal,
)
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.entitlement_bench import EntitlementBench


class BearerOfTheTest:
    """Signs in `person:<uuid>:<home>` tokens."""

    async def principal(self, bearer_token: str) -> Principal:
        """The person the token names."""
        kind, _, rest = bearer_token.partition(":")
        user, _, home = rest.partition(":")
        if kind != "person":
            raise AppError("invalid_token", HTTPStatus.UNAUTHORIZED)
        return Principal(UUID(user), Home(home), 0)


@dataclass
class Countries:
    """Each person's country, as identity's profile reader gives it."""

    by_person: dict[UUID, str | None] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: UUID) -> AccountProfile | None:
        """The person's profile with their country."""
        del session
        return AccountProfile("Person", "en", None, self.by_person.get(user_id))


@dataclass(frozen=True, slots=True)
class PeopleBench:
    """The HTTP client of the person's routes and what tests set."""

    http: httpx.AsyncClient
    countries: Countries
    entitlements: EntitlementBench
    inquiries: SalesInquiries


def bearer(person: tuple[Home, UUID]) -> dict[str, str]:
    """The Authorization header of a person."""
    home, user_id = person
    return {"Authorization": f"Bearer person:{user_id}:{home.value}"}


@pytest_asyncio.fixture
async def people(entitlements: EntitlementBench, valkey: Redis) -> AsyncIterator[PeopleBench]:
    """The bench over the slot's homes and Valkey."""
    countries = Countries()
    ports = PortDirectory()
    ports.install([AUTHENTICATOR.bind(BearerOfTheTest()), ACCOUNT_PROFILE_READER.bind(countries)])
    transactions = entitlements.homes.transactions
    meter = MinutesMeter(transactions, (entitlements.snapshots, ports), entitlements.clock)
    views = PeopleViews(transactions, (entitlements.snapshots, meter, ports), entitlements.clock)
    inquiries = SalesInquiries(transactions, entitlements.ledger_outbox)
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    routers = (
        build_plans_router(views, inquiries, ports, limiter),
        build_usage_router(views, ports),
    )
    async with client_of(build_probe_app(extra=routers).app) as http:
        yield PeopleBench(http, countries, entitlements, inquiries)
