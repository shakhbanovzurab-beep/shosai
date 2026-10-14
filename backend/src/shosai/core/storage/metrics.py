"""Metrics of the bucket requests of one process (blob-store skill "Monitor", §16.7).

Rate, outcome and latency per home's bucket and S3 operation (ADR 0044). The home, the
operation and the outcome come from closed sets; keys, owners and sizes never become labels.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter, Histogram

from shosai.core.kernel.homes import Home

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

# Бакет дома в России — 45 мс по сети от плоскости; хвост — повторы и большие объекты.
DURATION_BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)


class StorageMetrics:
    """Requests to each home's bucket by operation and outcome, and their duration."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._requests = Counter(
            "shosai_storage_requests",
            "Запросы к бакету дома по операции S3 и исходу",
            ("home", "operation", "outcome"),
            registry=registry,
        )
        self._duration = Histogram(
            "shosai_storage_request_duration_seconds",
            "Длительность запроса к бакету дома с повторами клиента",
            ("home", "operation"),
            buckets=DURATION_BUCKETS,
            registry=registry,
        )

    def record(
        self, home: Home, operation: StorageOperation, outcome: StorageOutcome, seconds: float
    ) -> None:
        """Count one request to the home's bucket and record how long it took."""
        self._requests.labels(home=home.value, operation=operation, outcome=outcome).inc()
        self._duration.labels(home=home.value, operation=operation).observe(seconds)
