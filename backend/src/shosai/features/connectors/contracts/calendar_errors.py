"""The refusals of `CALENDARS`, as the calendar slice meets them (plan §3.3)."""

from http import HTTPStatus

from shosai.core.kernel.errors import AppError


class CalendarCursorExpiredError(AppError):
    """The provider forgot the sync cursor: the calendar is synced again from scratch."""

    def __init__(self) -> None:
        super().__init__("calendar_cursor_expired", HTTPStatus.GONE)


class CalendarConflictError(AppError):
    """The event changed at the provider since its etag was read."""

    def __init__(self) -> None:
        super().__init__("calendar_conflict", HTTPStatus.PRECONDITION_FAILED)


class CalendarEventNotFoundError(AppError):
    """No such event, or a calendar the account cannot see."""

    def __init__(self) -> None:
        super().__init__("calendar_event_not_found", HTTPStatus.NOT_FOUND)


class CalendarUnsupportedError(AppError):
    """The connection's app is not a calendar Shosai syncs."""

    def __init__(self) -> None:
        super().__init__("calendar_unsupported", HTTPStatus.NOT_FOUND)
