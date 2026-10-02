"""One JSON line per event, with the process, request and trace context, never blocking."""

import asyncio
import logging
import queue
from uuid import UUID

import structlog
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry

from tests.core.observability.capture import captured_logs
from whisperer.core.config.roles import ProcessRole
from whisperer.core.config.values import LogLevel
from whisperer.core.kernel.homes import Home
from whisperer.core.observability.log_context import log_context
from whisperer.core.observability.logs import DroppingQueueHandler
from whisperer.core.observability.metrics import ObservabilityMetrics

USER_ID = UUID("01920000-0000-7000-8000-000000000001")
log = structlog.stdlib.get_logger("tests.observability")


def test_an_event_becomes_one_json_line_with_the_process_fields() -> None:
    with captured_logs(role=ProcessRole.WORKERS) as captured:
        log.info("Задача поставлена", queue="default", attempts=2)

    [line] = captured.lines()
    assert line["message"] == "Задача поставлена"
    assert line["level"] == "info"
    assert line["logger"] == "tests.observability"
    assert line["role"] == "workers"
    assert line["service"] == "whisperer"
    assert line["queue"] == "default"
    assert line["attempts"] == 2
    assert line["timestamp"].endswith("Z")
    assert "Задача поставлена" in captured.text()


def test_standard_library_loggers_share_the_renderer() -> None:
    with captured_logs() as captured:
        logging.getLogger("uvicorn.error").warning("Порт %s занят", 8000)

    [line] = captured.lines()
    assert line["message"] == "Порт 8000 занят"
    assert line["level"] == "warning"
    assert line["logger"] == "uvicorn.error"
    assert line["role"] == "api"


def test_lines_below_the_level_are_not_written() -> None:
    with captured_logs(level=LogLevel.WARNING) as captured:
        log.info("Подробность")
        log.warning("Важное")

    assert [line["message"] for line in captured.lines()] == ["Важное"]


def test_a_line_inside_a_span_carries_its_trace() -> None:
    tracer = TracerProvider(shutdown_on_exit=False).get_tracer("tests")

    with captured_logs() as captured:
        log.info("Вне спана")
        with tracer.start_as_current_span("request") as span:
            log.info("Внутри спана")
            logging.getLogger("sqlalchemy.engine").warning("Медленный запрос")
        context = span.get_span_context()

    outside, *inside = captured.lines()
    assert "trace_id" not in outside
    assert "span_id" not in outside
    for line in inside:
        assert line["trace_id"] == format(context.trace_id, "032x")
        assert line["span_id"] == format(context.span_id, "016x")


def test_the_context_of_a_unit_of_work_reaches_its_lines_only() -> None:
    with captured_logs() as captured:
        with log_context(request_id="req-1", home=Home.RU, user_id=USER_ID):
            log.info("Внутри")
            with log_context(request_id="req-2"):
                log.info("Вложенный")
            log.info("Снова внешний")
        log.info("Снаружи")

    inner, nested, outer_again, outside = captured.lines()
    assert (inner["request_id"], inner["home"], inner["user_id"]) == ("req-1", "ru", str(USER_ID))
    assert (nested["request_id"], nested["home"]) == ("req-2", "ru")
    assert outer_again["request_id"] == "req-1"
    assert not {"request_id", "home", "user_id"} & outside.keys()


async def test_concurrent_tasks_do_not_share_context() -> None:
    async def handle(request_id: str) -> None:
        with log_context(request_id=request_id):
            await asyncio.sleep(0.01)
            log.info("Запрос обработан", handled=request_id)

    with captured_logs() as captured:
        await asyncio.gather(*(handle(f"req-{number}") for number in range(20)))

    lines = captured.lines()
    assert len(lines) == 20
    assert all(line["request_id"] == line["handled"] for line in lines)


def test_an_exception_is_one_line_with_its_traceback_and_no_locals() -> None:
    def fail(password: str) -> None:
        message = "Сбой обработки"
        raise RuntimeError(message)

    # Секрет собирается при выполнении, чтобы его не было в строках исходника трассировки.
    secret = "-".join(["local", "variable", "secret"])
    with captured_logs() as captured:
        try:
            fail(secret)
        except RuntimeError:
            log.exception("Необработанная ошибка")

    [line] = captured.lines()
    assert line["message"] == "Необработанная ошибка"
    assert line["level"] == "error"
    assert "Traceback" in line["exception"]
    assert "RuntimeError: Сбой обработки" in line["exception"]
    assert secret not in captured.text()


def test_closing_writes_out_every_queued_line() -> None:
    with captured_logs() as captured:
        for number in range(500):
            log.info("Строка", number=number)

    assert [line["number"] for line in captured.lines()] == list(range(500))


def test_a_full_queue_drops_the_line_and_counts_it() -> None:
    registry = CollectorRegistry()
    handler = DroppingQueueHandler(queue.Queue(maxsize=2), ObservabilityMetrics(registry))
    record = logging.LogRecord("tests", logging.INFO, __file__, 1, "Строка", None, None)

    for _ in range(5):
        handler.enqueue(record)

    dropped = registry.get_sample_value(
        "whisperer_telemetry_dropped_total", {"signal": "logs", "reason": "queue_full"}
    )
    assert dropped == 3
