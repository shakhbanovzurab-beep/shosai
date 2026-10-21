"""The business calendar the tests run on: the platform's default zone (ADR 0058)."""

from shosai.core.kernel.business_calendar import BusinessCalendar

MOSCOW = BusinessCalendar.named("Europe/Moscow")
