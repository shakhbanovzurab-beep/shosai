"""Microsoft against recorded answers (connectors plan step 13): a work account refused by its
tenant ends with `admin_consent_required`; Entra's scopes and tenant are read right; a delta
link survives a restart; a `reauthorizationRequired` lifecycle event renews the subscription."""

import json
import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.authorize import ConnectRequest
from shosai.features.connectors.application.calendars import ConnectorCalendars
from shosai.features.connectors.application.callback import ProviderAnswer
from shosai.features.connectors.contracts.calendar_errors import (
    CalendarCursorExpiredError,
)
from shosai.features.connectors.contracts.calendars import (
    AttendeeResponse,
    ChangesQuery,
    WatchChannel,
    WatchRequest,
)
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.flows import ReturnKind, ReturnTarget
from shosai.features.connectors.infrastructure.providers.outlook_calendar import OutlookCalendar
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord, GrantRecord
from tests.features.connectors.microsoft_bench import DELTA, MicrosoftBench, microsoft

__all__ = ["microsoft"]


async def consent(
    bench: MicrosoftBench, user_id: uuid.UUID, answer: tuple[str | None, str | None, str | None]
) -> str:
    """Start Outlook Calendar's flow and come back with the given code or error."""
    handoff = await bench.authorizer.begin(
        ConnectRequest(user_id, Home.RU, App.OUTLOOK_CALENDAR, ReturnTarget(ReturnKind.POPUP))
    )
    state = parse_qs(urlsplit(handoff.authorize_url).query)["state"][0]
    code, error, description = answer
    return await bench.completer.complete(
        Provider.MICROSOFT, ProviderAnswer(state, code, error, description), handoff.cookie.value
    )


async def test_a_work_account_refused_by_its_tenant_waits_for_its_admin(
    microsoft: MicrosoftBench,
) -> None:
    refused = await consent(microsoft, uuid.uuid4(), (
        None, "access_denied", "AADSTS65001: The user or administrator has not consented.",
    ))  # fmt: skip

    assert refused.endswith("status=error&error=admin_consent_required")


async def test_a_connect_reads_entra_s_scopes_and_the_tenant(microsoft: MicrosoftBench) -> None:
    user_id = uuid.uuid4()

    done = await consent(microsoft, user_id, ("ok:anna", None, None))

    assert "status=connected" in done
    async with microsoft.homes.transactions.begin(
        TenancyScope(Home.RU, user_id), read_only=True
    ) as s:
        grant = await s.scalar(select(GrantRecord))
    assert grant is not None
    assert (grant.account_label, grant.provider_meta) == (
        "anna@contoso.com",
        {"tenant": "tenant-1"},
    )
    assert {"Calendars.ReadWrite", "offline_access", "openid"} <= set(grant.granted_scopes)


async def connected(bench: MicrosoftBench) -> tuple[TenancyScope, uuid.UUID]:
    """A person with Outlook Calendar connected, and the connection's id."""
    user_id = uuid.uuid4()
    await consent(bench, user_id, ("ok:anna", None, None))
    scope = TenancyScope(Home.RU, user_id)
    async with bench.homes.transactions.begin(scope, read_only=True) as session:
        found: uuid.UUID | None = await session.scalar(select(ConnectionRecord.id))
    assert found is not None
    return scope, found


async def test_a_delta_link_survives_a_restart_and_a_forgotten_one_resyncs(
    microsoft: MicrosoftBench,
) -> None:
    scope, connection_id = await connected(microsoft)
    calendars = microsoft.calendars

    first = await calendars.changes(scope, connection_id, ChangesQuery("cal-1"))
    last = await calendars.changes(
        scope, connection_id, ChangesQuery("cal-1", page=first.next_page)
    )
    # Другой процесс с курсором из базы: тот же адрес Graph, дословно.
    restarted = ConnectorCalendars(microsoft.access, {App.OUTLOOK_CALENDAR: OutlookCalendar()})
    later = await restarted.changes(scope, connection_id, ChangesQuery("cal-1", last.sync_cursor))
    with pytest.raises(CalendarCursorExpiredError):
        await calendars.changes(
            scope, connection_id, ChangesQuery("cal-1", f"{DELTA}?$deltatoken=stale")
        )

    assert (first.sync_cursor, last.sync_cursor) == (None, f"{DELTA}?$deltatoken=d1")
    assert last.removed == ("gone-1",)
    review = last.events[0]
    assert review.start.at == datetime(2026, 11, 3, 9, tzinfo=UTC)
    assert review.conference_url == "https://teams.microsoft.com/l/m"
    assert [(a.email, a.response) for a in review.attendees] == [
        ("boris@contoso.com", AttendeeResponse.TENTATIVE)
    ]
    assert later.sync_cursor == f"{DELTA}?$deltatoken=d2"
    assert any(url == f"{DELTA}?$deltatoken=d1" for _m, url, _b in microsoft.api.calls)


async def test_a_reauthorization_event_renews_the_subscription(microsoft: MicrosoftBench) -> None:
    scope, connection_id = await connected(microsoft)
    hook = "https://shosai.test/v1/integrations/microsoft/notifications"
    until = datetime(2026, 11, 30, tzinfo=UTC)

    channel = await microsoft.calendars.watch(
        scope, connection_id, WatchRequest("cal-1", "ignored", hook, "state-1", until)
    )
    batch = json.dumps({"value": [
        {"subscriptionId": "sub-1", "clientState": "state-1", "changeType": "updated",
         "resource": "me/events/ev-1"},
        {"subscriptionId": "sub-1", "clientState": "state-1",
         "lifecycleEvent": "reauthorizationRequired"},
    ]}).encode()  # fmt: skip
    changed, lifecycle = microsoft.calendars.notifications("outlook_calendar", {}, batch)
    renewed = await microsoft.calendars.renew(scope, connection_id, channel, until)
    await microsoft.calendars.stop(scope, connection_id, WatchChannel("sub-0", None, None))

    assert (changed.state, changed.resource_id, changed.token) == (
        "updated",
        "me/events/ev-1",
        "state-1",
    )
    assert lifecycle.state == "reauthorizationRequired"
    assert renewed is not None
    assert renewed.expires_at == datetime(2026, 11, 1, tzinfo=UTC)
    ((_m, _url, sent),) = [
        c for c in microsoft.api.calls if c[0] == "POST" and c[1].endswith("/subscriptions")
    ]
    assert json.loads(sent)["lifecycleNotificationUrl"] == hook
