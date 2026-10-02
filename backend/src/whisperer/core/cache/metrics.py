"""Metrics of the cache: hit rate and failures per namespace (caching skill, §16.7).

The namespace is a code declared by a slice, the operation and result come from closed
sets; the name inside a namespace is an id and never a label.
"""

from typing import Literal

from prometheus_client import CollectorRegistry, Counter

type CacheOperation = Literal["get", "set", "delete"]
type CacheResult = Literal["hit", "miss", "ok", "error"]


class CacheMetrics:
    """Operations of the cache by namespace and result."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._operations = Counter(
            "whisperer_cache_operations",
            "Операции кэша по пространству имён и результату",
            ("namespace", "operation", "result"),
            registry=registry,
        )

    def count(
        self, namespace: str, operation: CacheOperation, result: CacheResult, amount: int = 1
    ) -> None:
        """Count `amount` operations of one namespace with one result."""
        self._operations.labels(namespace=namespace, operation=operation, result=result).inc(amount)
