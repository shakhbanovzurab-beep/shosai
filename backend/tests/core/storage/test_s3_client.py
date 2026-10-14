"""The S3 boundary: errors translated, spans without keys, retries bounded, 503 for outages."""

import asyncio
from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from prometheus_client import CollectorRegistry

from shosai.core.config.sections import StorageSettings
from shosai.core.kernel.homes import Home
from shosai.core.storage.errors import (
    ObjectNotFoundError,
    ObjectsNotDeletedError,
    StorageRejectedError,
    StorageUnavailableError,
)
from shosai.core.storage.metrics import StorageMetrics
from shosai.core.storage.s3_client import MAX_ATTEMPTS, S3Calls, open_s3_client, translate
from shosai.core.storage.s3_objects import S3ObjectStorage
from tests.core.db.tcp_proxy import LOOPBACK
from tests.core.storage.adapters import slot_storage
from tests.harness.settings import HarnessSettings
from tests.harness.shared_services import SlotBucket

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

SECRET_KEY = "u-7/Анна Петрова — паспорт.pdf"
SERVICE_UNAVAILABLE = (
    b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
)


def client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "m"},
            "ResponseMetadata": {
                "RequestId": "r",
                "HostId": "h",
                "HTTPStatusCode": status,
                "HTTPHeaders": {},
                "RetryAttempts": 0,
            },
        },
        "GetObject",
    )


@pytest.mark.parametrize(
    ("code", "status", "outcome", "error"),
    [
        ("NoSuchKey", 404, "not_found", ObjectNotFoundError),
        ("404", 404, "not_found", ObjectNotFoundError),
        ("NoSuchUpload", 404, "not_found", ObjectNotFoundError),
        ("NoSuchBucket", 404, "rejected", StorageRejectedError),
        ("AccessDenied", 403, "rejected", StorageRejectedError),
        ("InvalidPart", 400, "rejected", StorageRejectedError),
        ("SlowDown", 503, "unavailable", StorageUnavailableError),
        ("", 502, "unavailable", StorageUnavailableError),
    ],
)
def test_a_refused_request_becomes_a_storage_error(
    code: str, status: int, outcome: str, error: type[Exception]
) -> None:
    seen_outcome, translated, _ = translate(client_error(code, status))

    assert (seen_outcome, type(translated)) == (outcome, error)


def test_an_outage_is_503_with_retry_after() -> None:
    error = StorageUnavailableError()

    assert (error.code, int(error.status)) == ("storage_unavailable", 503)
    assert error.params["retry_after_seconds"] == 5


@pytest.fixture
def spans() -> Iterator[tuple[TracerProvider, InMemorySpanExporter]]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider, exporter
    provider.shutdown()


async def test_requests_are_client_spans_that_never_name_the_key(
    bucket: SlotBucket, spans: tuple[TracerProvider, InMemorySpanExporter]
) -> None:
    provider, exporter = spans
    storage = slot_storage(bucket, provider)

    await storage.objects.put(SECRET_KEY, b"x", content_type="application/pdf")
    assert await storage.objects.head(SECRET_KEY + ".missing") is None

    put, head = exporter.get_finished_spans()
    assert (put.name, put.kind, put.status.status_code) == (
        "S3.PutObject",
        SpanKind.CLIENT,
        StatusCode.UNSET,
    )
    # «Нет такого объекта» — ответ, а не сбой: спан не красится ошибкой.
    assert (head.name, head.status.status_code) == ("S3.HeadObject", StatusCode.UNSET)
    for span in (put, head):
        assert span.attributes is not None
        assert span.attributes["rpc.method"] in {"PutObject", "HeadObject"}
        assert not any("Анна" in str(value) for value in span.attributes.values())
        assert not span.events


async def test_a_failing_bucket_is_tried_a_bounded_number_of_times(
    harness_settings: HarnessSettings,
) -> None:
    requests = 0

    async def unavailable(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal requests
        await reader.readuntil(b"\r\n\r\n")
        requests += 1
        writer.write(SERVICE_UNAVAILABLE)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(unavailable, LOOPBACK, 0)
    port = int(server.sockets[0].getsockname()[1])
    settings = elsewhere(
        harness_settings.services.storage[Home.RU], s3_endpoint_url=f"http://{LOOPBACK}:{port}"
    )
    registry = CollectorRegistry()
    async with open_s3_client(settings) as client:
        calls = S3Calls(Home.RU, settings.s3_bucket, StorageMetrics(registry), None)
        with pytest.raises(StorageUnavailableError):
            await S3ObjectStorage(client, calls).ping()
    server.close()
    await server.wait_closed()

    assert requests == MAX_ATTEMPTS
    outcome = {"home": "ru", "operation": "HeadBucket", "outcome": "unavailable"}
    assert registry.get_sample_value("shosai_storage_requests_total", outcome) == 1


async def test_wrong_credentials_are_refused_not_unavailable(
    harness_settings: HarnessSettings,
) -> None:
    settings = elsewhere(
        harness_settings.services.storage[Home.RU], s3_secret_access_key="wrong-secret"
    )
    async with open_s3_client(settings) as client:
        storage = S3ObjectStorage(
            client, S3Calls(Home.RU, settings.s3_bucket, StorageMetrics(CollectorRegistry()), None)
        )
        with pytest.raises(StorageRejectedError):
            await storage.ping()


def elsewhere(settings: StorageSettings, **changes: str) -> StorageSettings:
    """The test storage settings with some values replaced."""
    values = {
        "s3_endpoint_url": str(settings.s3_endpoint_url),
        "s3_region": settings.s3_region,
        "s3_bucket": settings.s3_bucket,
        "s3_access_key_id": settings.s3_access_key_id,
        "s3_secret_access_key": settings.s3_secret_access_key.get_secret_value(),
    }
    return StorageSettings.model_validate(values | changes)


async def test_a_connection_failure_is_an_outage() -> None:
    registry = CollectorRegistry()
    calls = S3Calls(Home.RU, "shosai-ru", StorageMetrics(registry), None)

    with pytest.raises(StorageUnavailableError):
        async with calls.call("HeadBucket"):
            raise EndpointConnectionError(endpoint_url="http://127.0.0.1:1")

    outcome = {"home": "ru", "operation": "HeadBucket", "outcome": "unavailable"}
    assert registry.get_sample_value("shosai_storage_requests_total", outcome) == 1


class RefusingBatchClient:
    """A bucket that keeps one object of every batch, as on a denied key."""

    async def delete_objects(self, **_request: object) -> dict[str, list[dict[str, str]]]:
        denied = "tests/slot-9/u-7/a.bin"
        return {"Errors": [{"Key": denied, "Code": "AccessDenied", "Message": "m"}]}


async def test_objects_left_by_a_batch_are_named_for_a_retry() -> None:
    calls = S3Calls(Home.RU, "shosai-ru", StorageMetrics(CollectorRegistry()), None)
    storage = S3ObjectStorage(cast("S3Client", RefusingBatchClient()), calls, "tests/slot-9/")

    with pytest.raises(ObjectsNotDeletedError, match="AccessDenied") as raised:
        await storage.delete_many(["u-7/a.bin", "u-7/b.bin"])

    assert raised.value.keys == ("u-7/a.bin",)
