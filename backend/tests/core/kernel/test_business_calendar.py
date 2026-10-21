"""The business calendar: days, Monday weeks and months in the business zone (ADR 0058)."""

from datetime import UTC, date, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from shosai.core.kernel.business_calendar import BusinessCalendar
from tests.doubles.business_calendar import MOSCOW

START = datetime(2026, 1, 1, tzinfo=UTC)
moments = st.integers(0, 3 * 365 * 24 * 60).map(lambda minutes: START + timedelta(minutes=minutes))
# Пояс с переходом на летнее время: в нём сутки бывают по 23 и 25 часов.
BERLIN = BusinessCalendar.named("Europe/Berlin")


def test_a_moment_at_22_30_utc_on_the_31st_falls_in_the_next_moscow_day_and_month() -> None:
    moment = datetime(2026, 10, 31, 22, 30, tzinfo=UTC)

    day, next_day = MOSCOW.day_window(moment)
    month, next_month = MOSCOW.month_window(moment)

    assert MOSCOW.date_of(moment) == date(2026, 11, 1)
    assert day == datetime(2026, 10, 31, 21, 0, tzinfo=UTC)
    assert next_day - day == timedelta(days=1)
    assert (month, next_month) == (
        datetime(2026, 10, 31, 21, 0, tzinfo=UTC),
        datetime(2026, 11, 30, 21, 0, tzinfo=UTC),
    )
    assert MOSCOW.zone_name == "Europe/Moscow"


@given(now=moments)
def test_each_window_holds_the_moment_and_starts_at_the_zone_s_midnight(now: datetime) -> None:
    for calendar in (MOSCOW, BERLIN):
        day, next_day = calendar.day_window(now)
        week, next_week = calendar.week_window(now)
        month, next_month = calendar.month_window(now)

        assert day <= now < next_day
        assert week <= now < next_week
        assert month <= now < next_month
        assert day.astimezone(calendar.zone).time() == next_day.astimezone(calendar.zone).time()
        assert week.astimezone(calendar.zone).weekday() == 0
        assert next_week.astimezone(calendar.zone).date() - week.date() == timedelta(days=7)
        assert month.astimezone(calendar.zone).day == next_month.astimezone(calendar.zone).day == 1
        assert calendar.date_of(day) == calendar.date_of(now)
