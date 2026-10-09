"""Metrics of the bucket requests of one process (blob-store skill "Monitor", §16.7).

Rate, outcome and latency per S3 operation. The operation and the outcome come from
closed sets; keys, owners and sizes never become labels.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Histogram

type StorageOperation = Literal[
    "PutObject",
    "GetObject",
    "HeadObject",
    "DeleteObject",
    "DeleteObjects",
    "ListObjectsV2",
    "HeadBucket",
    "CreateMultipartUpload",
    "ListParts",
    "CompleteMultipartUpload",
    "AbortMultipartUpload",
]
type StorageOutcome = Literal["ok", "not_found", "rejected", "unavailable"]

# Бакет в России — 45 мс по сети от плоскости; хвост — повторы и большие объекты.
DURATION_BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)


class StorageMetrics:
    """Requests to the bucket by operation and outcome, and their duration."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._requests = Counter(
            "shosai_storage_requests",
            "Запросы к бакету по операции S3 и исходу",
            ("operation", "outcome"),
            registry=registry,
        )
        self._duration = Histogram(
            "shosai_storage_request_duration_seconds",
            "Длительность запроса к бакету с повторами клиента",
            ("operation",),
            buckets=DURATION_BUCKETS,
            registry=registry,
        )

    def record(self, operation: StorageOperation, outcome: StorageOutcome, seconds: float) -> None:
        """Count one request and record how long it took."""
        self._requests.labels(operation=operation, outcome=outcome).inc()
        self._duration.labels(operation=operation).observe(seconds)
