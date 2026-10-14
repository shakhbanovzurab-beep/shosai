"""`/v1/unsubscribe` and `/email/{name}`: one suppression per link, the same answer for all."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.config.sections import WebSettings
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.images import load_email_images
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.page import UnsubscribePage
from shosai.core.email.routes import build_email_links_router
from shosai.core.email.unsubscribe import UnsubscribeMetrics, Unsubscribes
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.web.app import HttpTelemetry, build_http_app
from tests.core.email.bench import USER_ID, mail_bench, mail_links
from tests.core.email.test_links import V2_TOKEN, draft_token
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

ONE_CLICK = {"Content-Type": "application/x-www-form-urlencoded"}
FORGED = V2_TOKEN[:-2] + "AA"


@dataclass(frozen=True, slots=True)
class LinkApp:
    """The HTTP client of the app and the registry its counters are in."""

    http: httpx.AsyncClient
    registry: CollectorRegistry

    def sample(self, source: str, outcome: str) -> float:
        """How many links of the source reached the outcome."""
        labels = {"source": source, "outcome": outcome}
        found = self.registry.get_sample_value("shosai_email_unsubscribes_total", labels)
        return found or 0.0


@asynccontextmanager
async def link_app(transactions: HomeTransactions, valkey: Redis) -> AsyncIterator[LinkApp]:
    """The HTTP shell with core's mail-link routes over the slot."""
    registry = CollectorRegistry()
    unsubscribes = Unsubscribes(transactions, mail_links(), UnsubscribeMetrics(registry))
    limiter = RateLimiter(valkey, KeyValueMetrics(registry))
    router = build_email_links_router(unsubscribes, UnsubscribePage(), load_email_images(), limiter)
    telemetry = HttpTelemetry(registry, TracerProvider(shutdown_on_exit=False))
    app = build_http_app(WebSettings.model_validate({}), telemetry, [router])
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://shosai.example") as http:
        yield LinkApp(http, registry)


async def suppressions(run_slot: RunSlot) -> dict[str, list[tuple[str, str, str]]]:
    """The suppression rows of each home."""
    found: dict[str, list[tuple[str, str, str]]] = {}
    for home in Home:
        rows = await fetch_rows(
            run_slot.claimed.connections[home],
            "SELECT user_id::text AS user_id, kind, source FROM email_suppressions",
        )
        found[home.value] = [(row["user_id"], row["kind"], row["source"]) for row in rows]
    return found


async def test_the_page_asks_first_and_changes_nothing(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    async with link_app(homes.transactions, valkey) as app:
        page = await app.http.get(
            "/v1/unsubscribe", params={"t": V2_TOKEN}, headers={"Accept-Language": "ru-RU"}
        )
        forged = await app.http.get(
            "/v1/unsubscribe", params={"t": FORGED}, headers={"Accept-Language": "ru-RU"}
        )

    assert page.status_code == forged.status_code == 200
    assert "Отписаться от этих писем?" in page.text
    assert page.text.replace(V2_TOKEN, "") == forged.text.replace(FORGED, "")
    assert page.headers["Cache-Control"] == "no-store"
    assert page.headers["Referrer-Policy"] == "no-referrer"
    assert "form-action 'self'" in page.headers["Content-Security-Policy"]
    assert await suppressions(run_slot) == {"ru": [], "eu": []}


async def test_a_one_click_post_suppresses_once_without_cookies(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    async with link_app(homes.transactions, valkey) as app:
        answers = [
            await app.http.post(
                "/v1/unsubscribe",
                params={"t": V2_TOKEN},
                content="List-Unsubscribe=One-Click",
                headers=ONE_CLICK,
            )
            for _ in range(2)
        ]

    assert [answer.json() for answer in answers] == [{"unsubscribed": True}] * 2
    assert not app.http.cookies
    assert await suppressions(run_slot) == {
        "ru": [],
        "eu": [(str(USER_ID), "notification", "link")],
    }
    assert (app.sample("link", "applied"), app.sample("link", "repeated")) == (1, 1)


async def test_a_draft_link_from_its_form_suppresses_newsletters_in_the_russian_home(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    async with link_app(homes.transactions, valkey) as app:
        answer = await app.http.post(
            "/v1/unsubscribe", data={"token": draft_token(USER_ID)}, headers=ONE_CLICK
        )

    assert answer.json() == {"unsubscribed": True}
    assert await suppressions(run_slot) == {
        "ru": [(str(USER_ID), "newsletter", "draft_link")],
        "eu": [],
    }


async def test_a_forged_token_gets_the_same_answer_and_changes_nothing(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    async with link_app(homes.transactions, valkey) as app:
        answer = await app.http.post("/v1/unsubscribe", params={"t": FORGED})
        empty = await app.http.post("/v1/unsubscribe")

    assert answer.status_code == empty.status_code == 200
    assert answer.json() == empty.json() == {"unsubscribed": True}
    assert await suppressions(run_slot) == {"ru": [], "eu": []}
    assert app.sample("unknown", "refused") == 2


async def test_the_page_form_unsubscribes_and_shows_the_done_page(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    browser = {"Accept": "text/html,application/xhtml+xml", "Accept-Language": "ar"}
    async with link_app(homes.transactions, valkey) as app:
        posted = await app.http.post(
            "/v1/unsubscribe", data={"token": V2_TOKEN}, headers=ONE_CLICK | browser
        )
        done = await app.http.get(posted.headers["Location"], headers=browser)

    assert posted.status_code == 303
    assert posted.headers["Location"] == "/v1/unsubscribe?done=true"
    assert done.status_code == 200
    assert 'dir="rtl"' in done.text
    assert "تم إلغاء اشتراكك" in done.text
    assert "<form" not in done.text
    assert len((await suppressions(run_slot))["eu"]) == 1


async def test_after_the_link_notifications_are_skipped_and_account_mail_is_not(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    bench = mail_bench(homes.transactions, 1)
    async with link_app(homes.transactions, valkey) as app:
        await app.http.post("/v1/unsubscribe", params={"t": V2_TOKEN})
    sent = {}
    async with homes.transactions.begin(TenancyScope(Home.EU, USER_ID)) as session:
        for kind in (EmailKind.NOTIFICATION, EmailKind.ACCOUNT):
            mail = OutgoingEmail(
                recipient="person@example.org", kind=kind, template="probe.code", locale="en",
                params={"name": "Anna"}, secrets={"code": "1"}, user_id=USER_ID,
            )  # fmt: skip
            sent[kind] = await bench.port.enqueue(session, mail)

    assert sent[EmailKind.NOTIFICATION] is None
    assert sent[EmailKind.ACCOUNT] is not None


async def test_unsubscribing_is_limited_per_address(homes: DatabaseAccess, valkey: Redis) -> None:
    async with link_app(homes.transactions, valkey) as app:
        codes = [(await app.http.get("/v1/unsubscribe")).status_code for _ in range(12)]

    assert codes.count(429) >= 1
    assert codes[0] == 200
