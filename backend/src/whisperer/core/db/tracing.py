"""Client spans for the statements of a home's engine (target architecture §16.1, §16.8).

One span per statement, a child of whatever span is current: the request, the task or
the loop iteration. The query text is SQLAlchemy's parametrised SQL — placeholders, never
values — cut to a bounded length; parameters themselves never reach a span.
"""

import re
from typing import Final

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.semconv.attributes import db_attributes, error_attributes, server_attributes
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer
from sqlalchemy import event
from sqlalchemy.engine import Connection, ExceptionContext, ExecutionContext
from sqlalchemy.ext.asyncio import AsyncEngine

from whisperer.core.kernel.homes import Home

POSTGRESQL: Final = "postgresql"
HOME_ATTRIBUTE: Final = "whisperer.home"
QUERY_TEXT_LIMIT: Final = 2048
SPAN_KEY: Final = "whisperer.db_span"
# Первое слово выражения — имя операции; CTE (WITH …) так и называется, без разбора.
OPERATION = re.compile(r"\s*([A-Za-z]{1,16})")
UNKNOWN_OPERATION: Final = "QUERY"

type Parameters = object


def trace_statements(engine: AsyncEngine, home: Home, tracer_provider: TracerProvider) -> None:
    """Record a client span around every statement the engine executes."""
    tracer = tracer_provider.get_tracer(__name__)
    sync_engine = engine.sync_engine
    attributes: dict[str, str | int] = {
        db_attributes.DB_SYSTEM_NAME: POSTGRESQL,
        db_attributes.DB_NAMESPACE: sync_engine.url.database or "",
        server_attributes.SERVER_ADDRESS: sync_engine.url.host or "",
        server_attributes.SERVER_PORT: sync_engine.url.port or 0,
        HOME_ATTRIBUTE: home.value,
    }
    listener = StatementSpans(tracer, attributes)
    event.listen(sync_engine, "before_cursor_execute", listener.started)
    event.listen(sync_engine, "after_cursor_execute", listener.finished)
    event.listen(sync_engine, "handle_error", listener.failed)


class StatementSpans:
    """Starts a span before a statement and ends it after the result or the error."""

    def __init__(self, tracer: Tracer, attributes: dict[str, str | int]) -> None:
        self._tracer = tracer
        self._attributes = attributes

    def started(
        self,
        connection: Connection,
        _cursor: object,
        statement: str,
        _parameters: Parameters,
        _context: ExecutionContext | None,
        _executemany: object,
    ) -> None:
        """Open the statement's span; the connection runs one statement at a time."""
        operation = operation_name(statement)
        span = self._tracer.start_span(
            operation,
            kind=SpanKind.CLIENT,
            attributes={
                **self._attributes,
                db_attributes.DB_OPERATION_NAME: operation,
                db_attributes.DB_QUERY_TEXT: statement[:QUERY_TEXT_LIMIT],
            },
        )
        connection.info[SPAN_KEY] = span

    def finished(
        self,
        connection: Connection,
        _cursor: object,
        _statement: str,
        _parameters: Parameters,
        _context: ExecutionContext | None,
        _executemany: object,
    ) -> None:
        """End the span of a statement that returned."""
        span: Span | None = connection.info.pop(SPAN_KEY, None)
        if span is not None:
            span.end()

    def failed(self, context: ExceptionContext) -> None:
        """End the span of a failed statement with the error's type and SQLSTATE."""
        if context.connection is None:
            return
        span: Span | None = context.connection.info.pop(SPAN_KEY, None)
        if span is None:
            return
        error = context.original_exception
        span.set_attribute(error_attributes.ERROR_TYPE, type(error).__qualname__)
        sqlstate = getattr(error, "sqlstate", None)
        if isinstance(sqlstate, str):
            span.set_attribute(db_attributes.DB_RESPONSE_STATUS_CODE, sqlstate)
        # Текст ошибки сервера может процитировать значение строки — в спан он не идёт.
        span.set_status(Status(StatusCode.ERROR))
        span.end()


def operation_name(statement: str) -> str:
    """`SELECT`, `INSERT`, `WITH` …: the first keyword of the statement, upper-cased."""
    match = OPERATION.match(statement)
    return match.group(1).upper() if match else UNKNOWN_OPERATION
