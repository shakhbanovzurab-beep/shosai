"""Google's grants against its recorded behaviour (connectors plan step 9): Calendar then Drive
on one account make one grant and Gmail another; an unticked box leaves only its app waiting;
disconnecting Drive keeps the grant, disconnecting Gmail revokes it; Testing tells ahead."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)
from tests.features.connectors.google_bench import GoogleBench, Person, google

__all__ = ["google"]

API = "https://www.googleapis.com/auth/"


def someone() -> Person:
    """A new person in the Russian home."""
    return Home.RU, uuid.uuid4()


async def grants(bench: GoogleBench, person: Person) -> dict[str, GrantRecord]:
    """The person's grants by their application."""
    async with bench.homes.transactions.begin(TenancyScope(*person), read_only=True) as session:
        found = (await session.scalars(select(GrantRecord))).all()
    return {grant.client_key: grant for grant in found}


async def connections(bench: GoogleBench, person: Person) -> dict[str, ConnectionRecord]:
    """The person's connections by app."""
    async with bench.homes.transactions.begin(TenancyScope(*person), read_only=True) as session:
        found = (await session.scalars(select(ConnectionRecord))).all()
    return {connection.app: connection for connection in found}


async def test_calendar_then_drive_share_a_grant_and_gmail_has_its_own(
    google: GoogleBench,
) -> None:
    person = someone()

    await google.connect(person, App.GOOGLE_CALENDAR)
    google.google.hold_refresh = True
    drive = await google.connect(person, App.GOOGLE_DRIVE)
    asked_for_drive = set(google.google.asked)
    google.google.hold_refresh = False
    await google.connect(person, App.GMAIL)

    assert "status=connected" in drive
    assert asked_for_drive == {"openid", "email", f"{API}drive.file"}
    held = await grants(google, person)
    assert set(held) == {"google", "google_mail"}
    assert {f"{API}calendar.events", f"{API}drive.file", "email"} <= set(
        held["google"].granted_scopes
    )
    assert held["google"].external_account_id == "sub-anna"
    assert held["google"].account_label == "anna@gmail.com"
    apps = await connections(google, person)
    assert apps["google_calendar"].grant_id == apps["google_drive"].grant_id == held["google"].id
    assert apps["gmail"].grant_id == held["google_mail"].id
    async with google.homes.transactions.begin(TenancyScope(*person), read_only=True) as session:
        sealed = await session.scalar(
            select(GrantSecretRecord.refresh_token_enc).where(
                GrantSecretRecord.grant_id == held["google"].id
            )
        )
    # Ответ для Диска пришёл без refresh-токена: в силе остался выданный Календарю.
    assert sealed is not None
    assert google.keys.decrypt(sealed) == "refresh-main-client-1"


async def test_an_unticked_box_leaves_only_its_app_waiting(google: GoogleBench) -> None:
    person = someone()
    await google.connect(person, App.GOOGLE_CALENDAR)

    google.google.unticked = {f"{API}drive.file"}
    refused = await google.connect(person, App.GOOGLE_DRIVE)
    google.google.unticked = {f"{API}calendar.events"}
    drive = await google.connect(person, App.GOOGLE_DRIVE)

    assert refused.endswith("status=error&error=scope_missing")
    assert "status=connected" in drive
    apps = await connections(google, person)
    assert (apps["google_calendar"].status, apps["google_calendar"].problem) == (
        "needs_reconnect", "scope_missing",
    )  # fmt: skip
    assert apps["google_drive"].status == "active"
    async with google.homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as session:
        broken = (await session.scalars(
            select(OutboxMessage.payload).where(
                OutboxMessage.event_type == "connectors.connection.broken"
            )
        )).all()  # fmt: skip
    assert [(event["app"], event["problem"]) for event in broken] == [
        ("google_calendar", "scope_missing")
    ]


async def test_drive_leaves_the_grant_and_gmail_revokes_its_own(google: GoogleBench) -> None:
    person = someone()
    for app in (App.GOOGLE_CALENDAR, App.GOOGLE_DRIVE, App.GMAIL):
        await google.connect(person, app)
    scope = TenancyScope(*person)

    drive = await google.disconnector.disconnect(scope, App.GOOGLE_DRIVE)
    gmail = await google.disconnector.disconnect(scope, App.GMAIL)
    held = await grants(google, person)
    assert held["google_mail"].status == "revoking"
    await google.revoker.revoke_due(scope, held["google_mail"].id)

    assert drive.access_remains_at_provider is True
    assert gmail.access_remains_at_provider is False
    after = await grants(google, person)
    assert set(after) == {"google"}
    assert after["google"].status == "active"
    assert google.google.revoked == ["refresh-mail-client-3"]


async def test_a_testing_project_tells_when_to_reconnect(google: GoogleBench) -> None:
    person = someone()
    await google.connect(person, App.GOOGLE_CALENDAR)
    await google.connect(person, App.GMAIL)

    rows = {row.spec.app: row for row in await google.cabinet.rows(TenancyScope(*person))}

    gmail, calendar = rows[App.GMAIL], rows[App.GOOGLE_CALENDAR]
    assert calendar.reconnect_by is None
    assert gmail.connection is not None
    assert gmail.reconnect_by is not None
    consent_at = datetime.fromisoformat(str(gmail.connection.provider_meta["consent_at"]))
    assert gmail.reconnect_by - consent_at == timedelta(days=7)
