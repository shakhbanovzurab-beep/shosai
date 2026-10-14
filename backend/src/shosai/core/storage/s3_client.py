"""The aiobotocore client of a home's bucket and how one request to it runs (ADR 0044, 0015).

One client per home's bucket and process: the homes may sit at different providers. Timeouts
are explicit and retries bounded (§14 rule 8): connect 2 s, each socket read 20 s, the
standard retry mode with at most 3 attempts, which backs off with jitter and repeats only
throttling and transient failures. Path addressing works with every S3-compatible endpoint.
Checksums are added only where the S3 API requires them: a presigned upload would otherwise
demand a checksum header the client cannot know in advance, and providers other than AWS do
not all accept the newer default checksums.

Each request gets a client span and a metric; a failure is translated at this boundary, so
slices see the storage errors of `errors.py`, never botocore's. Keys may contain file names,
so they never enter a span, a metric or a log line.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final

from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from botocore.exceptions import BotoCoreError, ClientError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.semconv.attributes import error_attributes
from opentelemetry.trace import NoOpTracerProvider, SpanKind, Status, StatusCode

from shosai.core.config.sections import StorageSettings
from shosai.core.kernel.homes import Home
from shosai.core.observability.outage_log import OutageLog
from shosai.core.storage.errors import (
    ObjectNotFoundError,
    StorageRejectedError,
    StorageUnavailableError,
)
from shosai.core.storage.metrics import StorageMetrics, StorageOperation, StorageOutcome

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

CONNECT_TIMEOUT_SECONDS: Final = 2
READ_TIMEOUT_SECONDS: Final = 20
MAX_ATTEMPTS: Final = 3
# Как у пула Valkey: предел запросов в работе у процесса API (§4.3). Соединения
# открываются по требованию; подпись ссылок соединений не занимает.
MAX_POOL_CONNECTIONS: Final = 64
NOT_FOUND_CODES: Final = frozenset({"NoSuchKey", "NoSuchUpload", "NotFound", "404"})
UNAVAILABLE_CODES: Final = frozenset(
    {"SlowDown", "ServiceUnavailable", "InternalError", "RequestTimeout", "503", "500"}
)
FIRST_SERVER_ERROR_STATUS: Final = 500


def client_config() -> AioConfig:
    """Timeouts, bounded retries, path addressing and checksums only where required."""
    return AioConfig(
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        read_timeout=READ_TIMEOUT_SECONDS,
        retries={"mode": "standard", "total_max_attempts": MAX_ATTEMPTS},
        max_pool_connections=MAX_POOL_CONNECTIONS,
        tcp_keepalive=True,
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )


@asynccontextmanager
async def open_s3_client(settings: StorageSettings) -> AsyncIterator[S3Client]:
    """The process's client of a home's bucket endpoint; its connections close on exit."""
    session = get_session()
    async with session.create_client(
        "s3",
        region_name=settings.s3_region,
        endpoint_url=str(settings.s3_endpoint_url),
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        config=client_config(),
    ) as client:
        yield client


class S3Calls:
    """Runs requests to one bucket: a client span, a metric and the error translation."""

    def __init__(
        self,
        home: Home,
        bucket: str,
        metrics: StorageMetrics,
        tracer_provider: TracerProvider | None,
    ) -> None:
        self.home = home
        self.bucket = bucket
        self._metrics = metrics
        self._tracer = (tracer_provider or NoOpTracerProvider()).get_tracer(__name__)
        self._outages = OutageLog("Хранилище не ответило")

    @asynccontextmanager
    async def call(self, operation: StorageOperation) -> AsyncIterator[None]:
        """Wrap one request; a failure leaves as a storage error, never as botocore's."""
        started = time.perf_counter()
        outcome: StorageOutcome = "ok"
        with self._tracer.start_as_current_span(
            f"S3.{operation}",
            kind=SpanKind.CLIENT,
            attributes={
                "rpc.system": "aws-api",
                "rpc.service": "S3",
                "rpc.method": operation,
                "aws.s3.bucket": self.bucket,
                "shosai.home": self.home.value,
            },
            # Текст ошибки хранилища может назвать ключ, а в ключе бывает имя файла.
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield
            except ClientError as error:
                outcome, translated, code = translate(error)
                if outcome != "not_found":
                    span.set_attribute(error_attributes.ERROR_TYPE, code)
                    span.set_status(Status(StatusCode.ERROR))
                if outcome == "unavailable":
                    self._outages.failed(error, operation=operation)
                raise translated from error
            except (BotoCoreError, TimeoutError, OSError) as error:
                outcome = "unavailable"
                span.set_attribute(error_attributes.ERROR_TYPE, type(error).__qualname__)
                span.set_status(Status(StatusCode.ERROR))
                self._outages.failed(error, operation=operation)
                raise StorageUnavailableError from error
            finally:
                self._metrics.record(self.home, operation, outcome, time.perf_counter() - started)


def translate(error: ClientError) -> tuple[StorageOutcome, Exception, str]:
    """The outcome, the storage error and the S3 code of a refused request."""
    code = error.response.get("Error", {}).get("Code", "")
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    if code in NOT_FOUND_CODES:
        return "not_found", ObjectNotFoundError(), code
    if code in UNAVAILABLE_CODES or status >= FIRST_SERVER_ERROR_STATUS:
        return "unavailable", StorageUnavailableError(), code or str(status)
    rejected = code or str(status)
    return "rejected", StorageRejectedError(rejected), rejected
