"""The month's minutes: tombstones, the allowance, the upload pre-check, Free devices (step 4)."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.ports.keys import PortBinding
from shosai.features.billing.application.minutes import MinutesMeter
from shosai.features.billing.contracts import (
    MEETING_MINUTES,
    FreeDeviceTakenError,
    MinutesExhaustedError,
    UploadExceedsMinutesError,
)
from shosai.features.billing.domain.meters import MinutesLeft, tombstones_since
from tests.doubles.business_calendar import MOSCOW
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.entitlement_bench import EntitlementBench

MINUTE = 60


class LiveMeetings:
    """Meetings that still exist: a fixed number of seconds in any window."""

    def __init__(self, seconds: int) -> None:
        self._seconds = seconds

    async def recorded_seconds(
        self, session: AsyncSession, user_id: UUID, window: tuple[datetime, datetime]
    ) -> int:
        """The fixed seconds."""
        del session, user_id, window
        return self._seconds


def meter(bench: EntitlementBench, bindings: Sequence[PortBinding[object]] = ()) -> MinutesMeter:
    ports = PortDirectory()
    ports.install(bindings)
    return MinutesMeter(
        bench.homes.transactions, (bench.snapshots, ports), bench.clock, business=MOSCOW
    )


async def delete_meeting(
    bench: EntitlementBench, minutes: MinutesMeter, person: tuple[Home, UUID], start: datetime
) -> UUID:
    """A meeting of `start` deleted with its 30 minutes; its id."""
    meeting_id = uuid4()
    async with bench.homes.transactions.begin(TenancyScope(*person)) as session:
        await minutes.meeting_deleted(session, person[1], (meeting_id, start), 30 * MINUTE)
    return meeting_id


async def checked(
    bench: EntitlementBench, minutes: MinutesMeter, person: tuple[Home, UUID], device: str | None
) -> MinutesLeft:
    async with bench.homes.transactions.begin(TenancyScope(*person)) as session:
        return await minutes.check(session, person[1], device)


async def test_a_tombstone_counts_once_in_its_month_and_the_month_resets_in_the_business_zone(
    entitlements: EntitlementBench,
) -> None:
    minutes, person = meter(entitlements), (Home.RU, uuid4())
    start, _ = MOSCOW.month_window(entitlements.clock.now)
    last_month = start - timedelta(seconds=1)
    gone = await delete_meeting(entitlements, minutes, person, last_month)
    async with entitlements.homes.transactions.begin(TenancyScope(*person)) as session:
        await minutes.meeting_deleted(session, person[1], (gone, last_month), 30 * MINUTE)
        await minutes.meeting_deleted(session, person[1], (uuid4(), start - timedelta(days=62)), 60)
    await delete_meeting(entitlements, minutes, person, start)

    this_month = await minutes.used_seconds(*person, entitlements.clock.now)
    previous = await minutes.used_seconds(*person, last_month)

    assert (this_month, previous) == (30 * MINUTE, 30 * MINUTE)


async def test_a_tombstone_in_the_first_hours_of_the_previous_business_month_is_kept(
    entitlements: EntitlementBench,
) -> None:
    minutes, person = meter(entitlements), (Home.EU, uuid4())
    # Первые часы прошлого московского месяца — ещё последний день UTC-месяца двумя месяцами раньше:
    # его партицию хранит политика двух прошлых месяцев (ADR 0058).
    first_hours = tombstones_since(entitlements.clock.now, MOSCOW) + timedelta(minutes=30)
    await delete_meeting(entitlements, minutes, person, first_hours)

    previous = await minutes.used_seconds(*person, first_hours)

    assert first_hours.astimezone(UTC).month != MOSCOW.date_of(first_hours).month
    assert previous == 30 * MINUTE


async def test_the_allowance_refuses_at_the_limit_and_counts_live_meetings(
    entitlements: EntitlementBench,
) -> None:
    person = (Home.EU, uuid4())
    live = meter(entitlements, [MEETING_MINUTES.bind(LiveMeetings(60 * MINUTE))])
    plain = meter(entitlements)
    for _ in range(2):
        await delete_meeting(entitlements, plain, person, entitlements.clock.now)

    without = await checked(entitlements, plain, person, None)
    with pytest.raises(MinutesExhaustedError) as refused:
        await checked(entitlements, live, person, None)
    await delete_meeting(entitlements, plain, person, entitlements.clock.now)
    with pytest.raises(MinutesExhaustedError):
        await checked(entitlements, live, person, None)

    assert (without.limit_minutes, without.remaining_minutes) == (120, 60)
    assert (refused.value.status, refused.value.code) == (402, "minutes_exhausted")
    assert refused.value.params == {"limit_minutes": 120}


async def test_an_upload_longer_than_the_minutes_left_is_refused_before_processing(
    entitlements: EntitlementBench,
) -> None:
    person = (Home.RU, uuid4())
    minutes = meter(entitlements, [MEETING_MINUTES.bind(LiveMeetings(59 * MINUTE))])
    for _ in range(2):
        await delete_meeting(entitlements, minutes, person, entitlements.clock.now)

    async with entitlements.homes.transactions.begin(TenancyScope(*person)) as session:
        fits = await minutes.covers(session, person[1], MINUTE)
        with pytest.raises(UploadExceedsMinutesError) as refused:
            await minutes.covers(session, person[1], MINUTE + 1)

    assert fits.remaining_minutes == 1
    assert (refused.value.status, refused.value.params) == (402, {"remaining_minutes": 1})


async def test_one_free_account_per_device_and_paid_accounts_are_never_refused(
    entitlements: EntitlementBench,
) -> None:
    minutes = meter(entitlements)
    first, second, paid = (Home.RU, uuid4()), (Home.RU, uuid4()), (Home.RU, uuid4())
    plan = await created(entitlements.catalogue, "/v1/admin/plans", plan_draft("pro"))
    await entitlements.subscribe(paid, (plan, "pro"))

    claimed = await checked(entitlements, minutes, first, "Anna's MacBook Pro")
    again = await checked(entitlements, minutes, first, "anna's macbook pro ")
    with pytest.raises(FreeDeviceTakenError) as refused:
        await checked(entitlements, minutes, second, "Anna's MacBook Pro")
    elsewhere = await checked(entitlements, minutes, second, "Office PC")
    unrefused = await checked(entitlements, minutes, paid, "Anna's MacBook Pro")

    assert claimed == again == elsewhere
    assert (refused.value.status, refused.value.code) == (403, "free_plan_device_taken")
    assert unrefused.limit_minutes is None
