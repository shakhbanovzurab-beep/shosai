"""Span attributes that may carry user input never reach a span (target architecture §16.8).

Instrumentations put the raw path and query of a request into the span when it starts:
a share token in a path, a search phrase or an email in a query. The sampler is the hook
the SDK offers before a span exists; it records every span, like `ALWAYS_ON`, but without
those attributes. `http.route` — the template — is set after routing and stays.
"""

from collections.abc import Sequence
from typing import override

from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, Sampler, SamplingResult
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes

# Имена по семантическим соглашениям OpenTelemetry, текущие и прежние: путь, запрос,
# полный адрес, адрес клиента и его user agent.
PRIVATE_SPAN_ATTRIBUTES = frozenset(
    {
        "url.full",
        "url.path",
        "url.query",
        "http.url",
        "http.target",
        "client.address",
        "http.client_ip",
        "net.peer.ip",
        "user_agent.original",
        "http.user_agent",
    }
)


class PrivateAttributesSampler(Sampler):
    """Record every span and drop the start attributes that may carry user input."""

    @override
    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        """The `ALWAYS_ON` decision with the private attributes removed."""
        decision = ALWAYS_ON.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )
        kept = {
            key: value
            for key, value in (decision.attributes or {}).items()
            if key not in PRIVATE_SPAN_ATTRIBUTES
        }
        return SamplingResult(decision.decision, kept, decision.trace_state)

    @override
    def get_description(self) -> str:
        """Name of the sampler in diagnostics."""
        return "PrivateAttributesSampler{AlwaysOn}"
