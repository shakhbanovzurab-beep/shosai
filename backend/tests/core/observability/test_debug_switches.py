"""Debug switches in Valkey: on for at most an hour, read by every process (§16.7)."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import structlog
from redis.asyncio import Redis

from shosai.core.observability.debug_logs import DebugScope, DebugSwitch
from shosai.core.observability.debug_switches import (
    DEBUG_SWITCHES_KEY,
    DebugSwitches,
    following_debug_switches,
)
from shosai.core.observability.log_context import log_context
from tests.core.observability.capture import captured_logs

USER = uuid.UUID("0190f0f0-0000-7000-8000-0000000000d4")
ORG = uuid.UUID("0190f0f0-0000-7000-8000-0000000000d5")
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
LATER = timedelta(minutes=10)
log = structlog.stdlib.get_logger("shosai.tests.switches")


async def test_a_switch_is_on_until_its_end_and_then_gone(valkey: Redis) -> None:
    switches = DebugSwitches(valkey)

    await switches.switch_on(DebugScope.USER, USER, timedelta(minutes=30), NOW)
    await switches.switch_on(DebugScope.ORG, ORG, timedelta(minutes=5), NOW)

    on = await switches.active(NOW + timedelta(minutes=1))
    assert {(each.scope, each.target, each.ends_at) for each in on} == {
        (DebugScope.USER, USER, NOW + timedelta(minutes=30)),
        (DebugScope.ORG, ORG, NOW + timedelta(minutes=5)),
    }
    later = await switches.active(NOW + timedelta(minutes=5))
    assert [(each.scope, each.target) for each in later] == [(DebugScope.USER, USER)]
    assert await switches.active(NOW + timedelta(minutes=30)) == ()


async def test_switching_on_again_moves_the_end_and_off_ends_it(valkey: Redis) -> None:
    switches = DebugSwitches(valkey)
    await switches.switch_on(DebugScope.USER, USER, timedelta(minutes=5), NOW)

    await switches.switch_on(DebugScope.USER, USER, timedelta(minutes=20), NOW)
    [only] = await switches.active(NOW)
    assert only.ends_at == NOW + timedelta(minutes=20)

    assert await switches.switch_off(DebugScope.USER, USER)
    assert not await switches.switch_off(DebugScope.USER, USER)
    assert await switches.active(NOW) == ()


@pytest.mark.parametrize("duration", [timedelta(0), timedelta(minutes=61)])
async def test_a_switch_holds_for_at_most_an_hour(valkey: Redis, duration: timedelta) -> None:
    with pytest.raises(ValueError, match="60 минут"):
        await DebugSwitches(valkey).switch_on(DebugScope.USER, USER, duration, NOW)

    assert await valkey.exists(DEBUG_SWITCHES_KEY) == 0


async def test_switching_on_drops_the_switches_that_ended(valkey: Redis) -> None:
    switches = DebugSwitches(valkey)
    await switches.switch_on(DebugScope.ORG, ORG, timedelta(minutes=1), NOW)

    await switches.switch_on(DebugScope.USER, USER, timedelta(minutes=1), NOW + timedelta(hours=1))

    assert await valkey.zcard(DEBUG_SWITCHES_KEY) == 1


async def test_a_process_follows_the_switches_and_logs_each_change(valkey: Redis) -> None:
    switches = DebugSwitches(valkey)
    every = timedelta(milliseconds=50)

    with captured_logs() as logs:
        async with following_debug_switches(valkey, logs.debug_logs, every):
            await switches.switch_on(DebugScope.USER, USER, timedelta(minutes=5), datetime.now(UTC))
            await asyncio.sleep(0.2)
            with log_context(user_id=USER):
                log.debug("отладка во время переключателя")
            await switches.switch_off(DebugScope.USER, USER)
            await asyncio.sleep(0.2)
            with log_context(user_id=USER):
                log.debug("отладка после выключения")
        assert logging.getLogger("shosai").level == logging.NOTSET

    messages = [line["message"] for line in logs.lines()]
    assert "отладка во время переключателя" in messages
    assert "отладка после выключения" not in messages
    [on] = [line for line in logs.lines() if line["message"] == "Отладочные журналы включены"]
    assert on["user_id"] == str(USER)
    assert "Отладочные журналы выключены" in messages


async def test_valkey_out_of_reach_keeps_the_switches_the_process_has() -> None:
    unreachable = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1)

    with captured_logs() as logs:
        logs.debug_logs.apply([DebugSwitch(DebugScope.USER, USER, datetime.now(UTC) + LATER)])
        # Чтение ждёт Valkey не дольше секунды: блок переживает два таких чтения.
        async with following_debug_switches(unreachable, logs.debug_logs, timedelta(seconds=0.1)):
            await asyncio.sleep(1.5)
            with log_context(user_id=USER):
                log.debug("отладка без Valkey")
    await unreachable.aclose()

    messages = [line["message"] for line in logs.lines()]
    assert "отладка без Valkey" in messages
    warnings = [each for each in messages if each.startswith("Valkey недоступен: отладочные")]
    assert len(warnings) == 1
