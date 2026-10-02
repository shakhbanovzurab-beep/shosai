"""RED metrics and server spans of the public app, with no user input in either.

The draft lost every request to a 500 once an upgrade broke the metrics instrumentator;
these tests run the instrumentator and the native tracing together on every run.
"""

from opentelemetry.trace import SpanKind, StatusCode

from tests.core.observability.capture import captured_logs
from tests.core.web.probe_app import ITEM_ROUTE, build_probe_app, client_of
from whisperer.core.observability.span_privacy import PRIVATE_SPAN_ATTRIBUTES

PARENT_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{PARENT_TRACE_ID}-b7ad6b7169203331-01"


async def test_requests_are_counted_per_route_template_and_status_class() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        await client.get("/v1/probe/items/1")
        await client.get("/v1/probe/items/2")
        await client.get("/v1/probe/crash")
        await client.get("/v1/no/such/route")

    def requests(handler: str, status: str) -> float | None:
        labels = {"handler": handler, "method": "GET", "status": status}
        return probe.registry.get_sample_value("http_requests_total", labels)

    assert requests(ITEM_ROUTE, "2xx") == 2
    assert requests("/v1/probe/crash", "5xx") == 1
    assert requests("none", "4xx") == 1


async def test_one_server_span_per_request_named_by_its_template() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        await client.get("/v1/probe/items/42?q=someone@example.com")

    [span] = probe.finished_spans()
    assert span.kind is SpanKind.SERVER
    assert span.name == f"GET {ITEM_ROUTE}"
    attributes = dict(span.attributes or {})
    assert attributes["http.route"] == ITEM_ROUTE
    assert attributes["http.response.status_code"] == 200
    assert not PRIVATE_SPAN_ATTRIBUTES & set(attributes)
    assert "someone" not in str(attributes)


async def test_a_caller_trace_continues_and_reaches_the_log_lines() -> None:
    probe = build_probe_app()
    with captured_logs() as captured:
        async with client_of(probe.app) as client:
            await client.get("/v1/probe/items/1", headers={"traceparent": TRACEPARENT})

    [span] = probe.finished_spans()
    assert format(span.context.trace_id, "032x") == PARENT_TRACE_ID
    for line in captured.lines():
        assert line["trace_id"] == PARENT_TRACE_ID
        assert line["span_id"] == format(span.context.span_id, "016x")


async def test_an_unhandled_error_marks_the_span_failed() -> None:
    probe = build_probe_app()
    async with client_of(probe.app) as client:
        await client.get("/v1/probe/crash")

    [span] = probe.finished_spans()
    assert span.status.status_code is StatusCode.ERROR
    assert dict(span.attributes or {})["http.response.status_code"] == 500
