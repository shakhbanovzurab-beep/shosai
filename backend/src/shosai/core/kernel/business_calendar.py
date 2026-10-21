"""The business calendar: days, Monday weeks and months in the platform's business zone (ADR 0058).

Moments stay in UTC; only the boundaries of a total move. A business day runs from midnight to
midnight in the business zone (`BUSINESS_TIME_ZONE`, Europe/Moscow by default: 21:00 to 21:00
UTC), a week from Monday's midnight, a month from the first's. Every daily, weekly and monthly
total of money, AI spend and usage asks this calendar, never UTC, a browser or a profile.
Hours need none of it: a whole-hour zone shares UTC's hour boundaries.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAYS_IN_WEEK = 7
DECEMBER = 12


@dataclass(frozen=True, slots=True)
class BusinessCalendar:
    """Calendar periods in one IANA zone; every boundary is an aware moment in that zone."""

    zone: ZoneInfo

    @classmethod
    def named(cls, name: str) -> BusinessCalendar:
        """The calendar of a zone by its IANA name, such as `Europe/Moscow`."""
        return cls(ZoneInfo(name))

    @property
    def zone_name(self) -> str:
        """The zone's IANA name, as the admin panel and SQL's `date_trunc` take it."""
        return self.zone.key

    def date_of(self, at: datetime) -> date:
        """The business date a moment falls on."""
        return at.astimezone(self.zone).date()

    def midnight(self, day: date) -> datetime:
        """The first moment of a business date."""
        return datetime.combine(day, time(), tzinfo=self.zone)

    def day_window(self, at: datetime) -> tuple[datetime, datetime]:
        """The business day of a moment: its first moment and the next day's."""
        day = self.date_of(at)
        return self.midnight(day), self.midnight(day + timedelta(days=1))

    def week_window(self, at: datetime) -> tuple[datetime, datetime]:
        """The Monday week of a moment: Monday's midnight and the next Monday's."""
        day = self.date_of(at)
        monday = day - timedelta(days=day.weekday())
        return self.midnight(monday), self.midnight(monday + timedelta(days=DAYS_IN_WEEK))

    def month_window(self, at: datetime) -> tuple[datetime, datetime]:
        """The calendar month of a moment: the first's midnight and the next month's."""
        first = self.date_of(at).replace(day=1)
        if first.month == DECEMBER:
            following = first.replace(year=first.year + 1, month=1)
        else:
            following = first.replace(month=first.month + 1)
        return self.midnight(first), self.midnight(following)
