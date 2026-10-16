"""DEBUG lines of a switched-on user or company only, until the switch ends (§16.7)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import structlog

from shosai.core.config.values import LogLevel
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.observability.debug_logs import OWN_LOGGERS, DebugScope, DebugSwitch
from shosai.core.observability.log_context import late_log_fields, log_context
from tests.core.observability.capture import captured_logs
from tests.harness.database_access import DatabaseAccess

SWITCHED = uuid.UUID("0190f0f0-0000-7000-8000-0000000000d1")
OTHER = uuid.UUID("0190f0f0-0000-7000-8000-0000000000d2")
COMPANY = uuid.UUID("0190f0f0-0000-7000-8000-0000000000d3")
log = structlog.stdlib.get_logger("shosai.tests.debug")


def switch(scope: DebugScope, target: uuid.UUID, minutes: float = 10) -> DebugSwitch:
    """A switch ending `minutes` from now; negative minutes, one already ended."""
    return DebugSwitch(scope, target, datetime.now(UTC) + timedelta(minutes=minutes))


def debug_messages(lines: list[dict[str, object]]) -> list[object]:
    """The messages of the DEBUG lines."""
    return [line["message"] for line in lines if line["level"] == "debug"]


def test_without_a_switch_no_debug_line_is_written_and_the_level_is_the_configured_one() -> None:
    with captured_logs() as logs, log_context(user_id=SWITCHED):
        log.debug("строка отладки")
        log.info("строка обычная")

    assert debug_messages(logs.lines()) == []
    assert [line["message"] for line in logs.lines()] == ["строка обычная"]
    assert logging.getLogger(OWN_LOGGERS).level == logging.NOTSET


def test_a_switched_user_gets_debug_lines_and_another_user_does_not() -> None:
    with captured_logs() as logs:
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED)])
        with log_context(user_id=SWITCHED):
            log.debug("отладка включённого")
        with log_context(user_id=OTHER):
            log.debug("отладка другого")
            log.info("обычная строка другого")
        log.debug("отладка без пользователя")
        log.debug("отладка с явным полем", user_id=str(SWITCHED))

    assert debug_messages(logs.lines()) == ["отладка включённого", "отладка с явным полем"]
    assert "обычная строка другого" in [line["message"] for line in logs.lines()]


def test_a_switched_company_opens_the_lines_of_its_work() -> None:
    with captured_logs() as logs:
        logs.debug_logs.apply([switch(DebugScope.ORG, COMPANY)])
        with log_context(org_id=COMPANY, user_id=OTHER):
            log.debug("отладка компании")
        with log_context(user_id=OTHER):
            log.debug("отладка вне компании")

    assert debug_messages(logs.lines()) == ["отладка компании"]


def test_a_caller_learned_midway_is_matched_through_the_late_fields() -> None:
    with captured_logs() as logs:
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED)])
        with late_log_fields(lambda: {"user_id": SWITCHED}):
            log.debug("отладка после аутентификации")

    assert debug_messages(logs.lines()) == ["отладка после аутентификации"]


def test_the_lines_stop_at_the_end_even_before_the_switches_are_read_again() -> None:
    with captured_logs() as logs, log_context(user_id=SWITCHED):
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED, minutes=-0.01)])
        log.debug("отладка после конца")

    assert debug_messages(logs.lines()) == []


def test_switching_off_returns_the_configured_level() -> None:
    with captured_logs() as logs, log_context(user_id=SWITCHED):
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED)])
        assert logging.getLogger(OWN_LOGGERS).level == logging.DEBUG
        logs.debug_logs.apply([])
        log.debug("отладка после выключения")

    assert debug_messages(logs.lines()) == []
    assert logging.getLogger(OWN_LOGGERS).level == logging.NOTSET


def test_libraries_stay_at_the_configured_level_while_a_switch_is_on() -> None:
    with captured_logs() as logs, log_context(user_id=SWITCHED):
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED)])
        logging.getLogger("sqlalchemy.engine.probe").debug("SELECT … с параметрами")
        logging.getLogger("some_library").debug("заголовки запроса")

    assert debug_messages(logs.lines()) == []


def test_a_process_configured_for_debug_keeps_every_debug_line() -> None:
    with captured_logs(LogLevel.DEBUG) as logs, log_context(user_id=OTHER):
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED)])
        log.debug("отладка при уровне DEBUG")

    assert debug_messages(logs.lines()) == ["отладка при уровне DEBUG"]


async def test_a_switched_users_transaction_is_one_debug_line_with_its_ids_as_text(
    homes: DatabaseAccess,
) -> None:
    with captured_logs() as logs:
        logs.debug_logs.apply([switch(DebugScope.USER, SWITCHED)])
        for user in (SWITCHED, OTHER):
            async with homes.transactions.begin(TenancyScope(Home.EU, user, None), read_only=True):
                pass

    [line] = [each for each in logs.lines() if each["message"] == "Транзакция зафиксирована"]
    assert (line["level"], line["user_id"], line["home"]) == ("debug", str(SWITCHED), "eu")
    assert "org_id" not in line
    assert isinstance(line["duration_ms"], float)
