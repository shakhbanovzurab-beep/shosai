"""Reading the HTTP samples of a registry in tests."""

from prometheus_client import CollectorRegistry

from shosai.core.web.http_metrics import DURATION_METRIC, LABELS

type RequestLabels = tuple[str, str, str, str, str]


def samples(registry: CollectorRegistry) -> list[tuple[str, dict[str, str], float]]:
    """Every HTTP sample except the `_created` timestamps."""
    return [
        (sample.name, sample.labels, sample.value)
        for family in registry.collect()
        if family.name.startswith("http_")
        for sample in family.samples
        if not sample.name.endswith("_created")
    ]


def requests_counted(registry: CollectorRegistry) -> dict[RequestLabels, float]:
    """Requests by (method, route, status code, scheme, error type): the histogram's count."""
    counted: dict[RequestLabels, float] = {}
    for name, labels, value in samples(registry):
        if name == f"{DURATION_METRIC}_count":
            method, route, status, scheme, error = (labels[label] for label in LABELS)
            counted[method, route, status, scheme, error] = value
    return counted
