"""Structured logs: one JSON line per event on stdout (target architecture §16.1).

structlog loggers and standard-library loggers (uvicorn, drivers, clients) share one
renderer. A line is rendered in the caller's thread — so it sees the caller's context and
active span — and handed to a writer thread through a bounded queue: a slow stdout never
blocks the event loop, and lines that do not fit are dropped and counted.

Messages are Russian, keys are English. Every line carries `role`, `service`, and inside
a span `trace_id` and `span_id`; `log_context` adds the ids of the unit of work.
"""

import logging
import queue
import sys
from dataclasses import dataclass
from logging.handlers import QueueHandler, QueueListener
from typing import TextIO

import structlog
from opentelemetry import trace
from structlog.typing import EventDict, Processor, WrappedLogger

from whisperer.core.config.roles import ProcessRole
from whisperer.core.config.sections import ObservabilitySettings
from whisperer.core.observability.metrics import ObservabilityMetrics
from whisperer.core.observability.redaction import redact_event

LOG_QUEUE_CAPACITY = 10_000
# Библиотеки, чьи INFO и DEBUG заглушают наши строки или выдают лишнее; шаги F1 дополняют
# список своими. HTTPX пишет на INFO каждый исходящий запрос с полным адресом, где бывают
# ключи и токены в строке запроса. uvicorn.access дублирует строку доступа границы запроса
# (core/web/boundary.py), но с сырым путём, строкой запроса и адресом клиента (§16.8).
QUIET_LIBRARY_LOGGERS = ("urllib3", "httpx", "httpcore", "uvicorn.access")


class DroppingQueueHandler(QueueHandler):
    """Queues a rendered record without waiting; a full queue drops the record and counts it."""

    def __init__(
        self, log_queue: queue.Queue[logging.LogRecord], metrics: ObservabilityMetrics
    ) -> None:
        super().__init__(log_queue)
        self._log_queue = log_queue
        self._metrics = metrics

    def enqueue(self, record: logging.LogRecord) -> None:
        """Put the record into the queue or drop it; never wait for the writer."""
        try:
            self._log_queue.put_nowait(record)
        except queue.Full:
            self._metrics.count_dropped("logs", "queue_full")


@dataclass(frozen=True, slots=True)
class LoggingPipeline:
    """The configured pipeline of a process; `close` writes out what is queued."""

    handler: DroppingQueueHandler
    listener: QueueListener
    previous_root_level: int

    def close(self) -> None:
        """Write out the queued lines, detach from the root logger and reset structlog."""
        root = logging.getLogger()
        root.removeHandler(self.handler)
        root.setLevel(self.previous_root_level)
        self.listener.stop()
        structlog.reset_defaults()


def configure_logging(
    settings: ObservabilitySettings,
    role: ProcessRole,
    metrics: ObservabilityMetrics,
    stream: TextIO = sys.stdout,
) -> LoggingPipeline:
    """Route structlog and standard-library logging of the process into JSON lines on `stream`."""
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(LOG_QUEUE_CAPACITY)
    handler = DroppingQueueHandler(log_queue, metrics)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processors=line_processors(settings, role))
    )
    writer = logging.StreamHandler(stream)
    writer.setFormatter(logging.Formatter("%(message)s"))
    listener = QueueListener(log_queue, writer)

    root = logging.getLogger()
    previous_root_level = root.level
    root.setLevel(settings.log_level.value)
    root.addHandler(handler)
    for name in QUIET_LIBRARY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # Без кэша: тесты перенастраивают конвейер, а закэшированный логгер держал бы старый.
        cache_logger_on_first_use=False,
    )
    listener.start()
    return LoggingPipeline(handler, listener, previous_root_level)


def line_processors(settings: ObservabilitySettings, role: ProcessRole) -> list[Processor]:
    """The processors that turn an event of either logging API into one JSON line."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        process_fields(role, settings.otel_service_name),
        add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        # После трассировки исключения: пароль в адресе из текста ошибки тоже затирается.
        redact_event,
        structlog.processors.EventRenamer("message"),
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ]


def process_fields(role: ProcessRole, service: str) -> Processor:
    """A processor adding the process role and the service name to every line."""

    def add_process_fields(
        _logger: WrappedLogger, _method: str, event_dict: EventDict
    ) -> EventDict:
        event_dict["role"] = role.value
        event_dict["service"] = service
        return event_dict

    return add_process_fields


def add_trace_context(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """`trace_id` and `span_id` of the active span, so a line leads to its trace and back."""
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict
