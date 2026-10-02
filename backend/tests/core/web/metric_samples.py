"""Reading the HTTP samples of a registry in tests."""

from prometheus_client import CollectorRegistry


def samples(registry: CollectorRegistry) -> list[tuple[str, dict[str, str], float]]:
    """Every HTTP sample except the `_created` timestamps."""
    return [
        (sample.name, sample.labels, sample.value)
        for family in registry.collect()
        if family.name.startswith("http_")
        for sample in family.samples
        if not sample.name.endswith("_created")
    ]


def requests_total(registry: CollectorRegistry) -> dict[tuple[str, str, str], float]:
    """`http_requests_total` by (method, status, handler)."""
    return {
        (labels["method"], labels["status"], labels["handler"]): value
        for name, labels, value in samples(registry)
        if name == "http_requests_total"
    }
