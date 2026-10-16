"""Where a person's data could reach telemetry: log lines, spans, metric labels (§16.8).

A test drives a slice's flows with canary values — an address, a name, a password, the codes
and tokens the flows hand out, the client's address and agent — and `leaks` names every
canary found anywhere in what the run emitted. Each slice adds its own flows this way
(docs/observability.md).
"""

from collections.abc import Iterable, Iterator, Mapping, Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.util.types import Attributes
from prometheus_client import CollectorRegistry


def attribute_texts(attributes: Attributes) -> Iterator[str]:
    """Keys and values of span attributes as text."""
    for key, value in (attributes or {}).items():
        yield key
        yield str(value)


def span_texts(span: ReadableSpan) -> Iterator[str]:
    """Everything a span carries to Tempo: name, attributes, events, links, status, resource."""
    yield span.name
    yield from attribute_texts(span.attributes)
    for event in span.events:
        yield event.name
        yield from attribute_texts(event.attributes)
    for link in span.links:
        yield from attribute_texts(link.attributes)
    if span.status.description:
        yield span.status.description
    yield from attribute_texts(span.resource.attributes)


def metric_texts(registry: CollectorRegistry) -> Iterator[str]:
    """Every label value and exemplar label of a registry: what a scrape would read."""
    for family in registry.collect():
        for sample in family.samples:
            yield from sample.labels.values()
            if sample.exemplar is not None:
                yield from sample.exemplar.labels.values()


def leaks(
    canaries: Mapping[str, str],
    log_text: str,
    spans: Sequence[ReadableSpan],
    registries: Iterable[CollectorRegistry],
) -> dict[str, list[str]]:
    """Each canary found, with the places it was found in; empty when nothing leaked."""
    places = {
        "logs": [log_text],
        "spans": [text for span in spans for text in span_texts(span)],
        "metrics": [text for registry in registries for text in metric_texts(registry)],
    }
    found: dict[str, list[str]] = {}
    for name, value in canaries.items():
        needle = value.lower()
        hits = [place for place, texts in places.items() if any(needle in t.lower() for t in texts)]
        if hits:
            found[name] = hits
    return found
