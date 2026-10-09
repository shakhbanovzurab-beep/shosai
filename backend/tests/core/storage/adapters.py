"""The storage adapters over the run's prefix of the bucket, each with its own metrics."""

from dataclasses import dataclass

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry

from shosai.core.storage.metrics import StorageMetrics
from shosai.core.storage.s3_client import S3Calls
from shosai.core.storage.s3_multipart import S3MultipartUploads
from shosai.core.storage.s3_objects import S3ObjectStorage
from tests.harness.shared_services import SlotBucket


@dataclass(frozen=True, slots=True)
class SlotStorage:
    """Objects and uploads confined to the run's prefix, and the registry they report to."""

    objects: S3ObjectStorage
    uploads: S3MultipartUploads
    registry: CollectorRegistry

    def requests(self, operation: str, outcome: str) -> float:
        """How many requests of an operation ended with an outcome."""
        labels = {"operation": operation, "outcome": outcome}
        return self.registry.get_sample_value("shosai_storage_requests_total", labels) or 0.0


def slot_storage(bucket: SlotBucket, tracer_provider: TracerProvider | None = None) -> SlotStorage:
    """Adapters as a process builds them, under the run's root prefix."""
    registry = CollectorRegistry()
    calls = S3Calls(bucket.bucket, StorageMetrics(registry), tracer_provider)
    return SlotStorage(
        objects=S3ObjectStorage(bucket.client, calls, bucket.root),
        uploads=S3MultipartUploads(bucket.client, calls, bucket.root),
        registry=registry,
    )
