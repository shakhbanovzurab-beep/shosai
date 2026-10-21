"""The admin's catalogue routes over the slot's EU home, with a stand-in admin session.

The plan table keeps the Free plan the migration seeded, so the harness does not empty
it: `catalogue` snapshots the table before a test and puts it back after.
"""

from collections.abc import AsyncIterator, Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest_asyncio
from psycopg.types.json import Jsonb

from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.application.catalogue import Catalogue, PlanHolding
from shosai.features.billing.application.promo_codes import PromoCodes
from shosai.features.billing.channels.http.admin_plans import build_admin_plans_router
from shosai.features.billing.channels.http.admin_promo_codes import (
    build_admin_promo_codes_router,
)
from shosai.features.identity.contracts import ADMIN_COOKIE, ADMIN_GATE
from tests.core.web.probe_app import build_probe_app, client_of
from tests.doubles.business_calendar import MOSCOW
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

ADMIN_SESSION = "bench-admin-session"
TODAY = datetime(2026, 10, 17, 12, tzinfo=UTC)
SNAPSHOT_SQL = "SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb) FROM tariffs t"
RESTORE_SQL = "INSERT INTO tariffs SELECT * FROM jsonb_populate_recordset(NULL::tariffs, %s)"


class BenchGate:
    """Admits the bench's admin session only."""

    async def admitted(self, cookie: str | None) -> bool:
        """Whether the cookie is the bench's session."""
        return cookie == ADMIN_SESSION


@dataclass
class CountedSubscribers:
    """Subscribers per plan as the test sets them; a held plan is also referenced."""

    by_plan: dict[UUID, int] = field(default_factory=dict)
    changes: list[str] = field(default_factory=list)

    async def counts(self, plan_ids: Collection[UUID]) -> Mapping[UUID, PlanHolding]:
        """The test's counts, nobody for the rest."""
        return {plan: PlanHolding(*[self.by_plan.get(plan, 0)] * 2) for plan in plan_ids}

    async def catalogue_changed(self) -> None:
        """Remember that the catalogue changed."""
        self.changes.append("catalogue")


@dataclass(frozen=True, slots=True)
class CatalogueBench:
    """The admin's client and the subscriber counts the catalogue sees."""

    admin: httpx.AsyncClient
    anonymous: httpx.AsyncClient
    subscribers: CountedSubscribers


@pytest_asyncio.fixture
async def catalogue(homes: DatabaseAccess, run_slot: RunSlot) -> AsyncIterator[CatalogueBench]:
    """The bench over the slot; the plan table is as the migration left it afterwards."""
    connection = run_slot.claimed.connections[Home.EU]
    snapshot = await fetch_value(connection, SNAPSHOT_SQL)
    subscribers = CountedSubscribers()
    ports = PortDirectory()
    ports.install([ADMIN_GATE.bind(BenchGate())])
    routers = (
        build_admin_plans_router(
            Catalogue(homes.transactions, (subscribers, subscribers), clock=lambda: TODAY), ports
        ),
        build_admin_promo_codes_router(
            PromoCodes(homes.transactions, clock=lambda: TODAY, business=MOSCOW), ports
        ),
    )
    app = build_probe_app(extra=routers).app
    try:
        async with client_of(app) as admin, client_of(app) as anonymous:
            admin.cookies.set(ADMIN_COOKIE, ADMIN_SESSION)
            yield CatalogueBench(admin, anonymous, subscribers)
    finally:
        await connection.execute("DELETE FROM promo_codes")
        await connection.execute("DELETE FROM tariffs")
        await connection.execute(RESTORE_SQL, (Jsonb(snapshot),))


def plan_draft(slug: str, **changes: object) -> dict[str, Any]:
    """A paid individual plan as the admin's form sends it."""
    draft: dict[str, Any] = {
        "name": slug.title(), "slug": slug, "description": "", "audience": "individual",
        "seats": None, "custom_pricing": False,
        "price_monthly": {"RUB": 149_000, "USD": 1_500, "EUR": 1_400},
        "price_yearly": {"RUB": 1_490_000, "USD": 15_000, "EUR": 14_000},
        "limits": {
            "meeting_minutes_per_month": None, "file_manager_gb": 100, "knowledge_base_mb": 100,
        },
        "capabilities": {
            "shared_workspace": False, "member_management": False, "centralized_billing": False,
            "sso": False, "admin_controls": False, "priority_support": False,
            "usage_analytics": False,
        },
        "features": ["Everything in Free"], "is_active": True, "is_featured": False,
        "sort_order": 10,
    }  # fmt: skip
    return {**draft, **changes}


def promo_draft(code: str, **changes: object) -> dict[str, Any]:
    """A percent code on every plan as the admin's form sends it."""
    draft: dict[str, Any] = {
        "code": code, "discount_type": "percent", "percent_off": 20, "amounts_off": {},
        "scope": "all", "plan_ids": [], "billing_period": "both", "max_redemptions": None,
        "per_user_limit": None, "valid_from": None, "valid_until": None,
        "first_payment_only": False, "is_active": True,
    }  # fmt: skip
    return {**draft, **changes}


async def created(bench: CatalogueBench, path: str, draft: dict[str, Any]) -> str:
    """A plan or promo code created through its route; its id."""
    answer = await bench.admin.post(path, json=draft)
    assert answer.status_code == 201, answer.text
    return str(answer.json()["id"])
