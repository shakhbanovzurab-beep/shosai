# ADR 0012 — HTTP metrics recorded by the request boundary

- **Status:** accepted by the owner on 2026-10-02 (F1 open item F1-O1); implemented after F1 step 3. **Amended 2026-10-13** by the owner's decision OD-3 of the [F1 audit](../plan/audits/F1-audit.md): names and labels follow the OpenTelemetry semantic conventions (see "Amendment"); decisions 1, 3 and 5 stand.
- **Package:** F1, backend foundation; every slice's routes are measured by it.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §3, §16.1, §16.7, §16.8, §18.2; [ADR 0008](0008-error-envelope-with-compatible-detail.md); [F1 plan](../plan/packages/F1-backend-foundation.md) (F1-O1); [CLAUDE.md](../../.claude/CLAUDE.md) "Performance", "Dependencies".

## Context

§16.1 and §18.2 named prometheus-fastapi-instrumentator 8.1.0 for the HTTP metrics. F1 step 3 wired it into the public app and measured it.

- **It matches every request a second time.** The instrumentator is a middleware outside routing. Before the app runs, it flattens every included router (`effective_route_contexts()`, 632 calls on a 600-route app) and matches the path against the whole route table again. FastAPI keeps its own routing result in private structures, so a third-party middleware has no public way to read it. On 600 routes (the draft has 588) the last route costs 1905 `matches()` calls instead of FastAPI's own 1304.
- **Cost.** In one configuration (600 routes, real logging pipeline, process tracer provider, one request mix), a sequential run costs 975 µs of CPU per request with the instrumentator, against 717 µs for the same boundary without metrics. So the instrumentator alone costs 258 µs per request. At 116 req/s (§3) that is ≈ 3% of a core; at the 100 000 DAU verification point ≈ 30%. Under an open load of 700–800 req/s on one process it saturates the core (97–102%) and p99 grows to 45–1100 ms; the same process without it stays at 84–92% and p99 7–9 ms.
- **User input reaches labels (§16.7, §16.8).**
  - A path that differs from a route only by a trailing slash is reported under its raw path, for example `handler="/v1/probe/items/someone@example.com/"`. Each id is a new series.
  - The `method` label is the raw method, so any token a client sends becomes a series (h11, which uvicorn uses without httptools, accepts any token).
  - A fuzz run of 3000 requests produced 10 raw paths and 7 invented methods. No configuration option prevents either.
- **A malformed `Content-Length`** (for example the byte `0xB9`) makes it raise in the middle of recording. Two of its five metrics are lost and a spurious error is logged.
- **The draft lost every request to a 500** when a Starlette upgrade broke this library's internals.

## Decision

1. The request boundary (`core/web/boundary.py`), which already writes one access line per request, records the HTTP metrics from the same outcome through `core/web/http_metrics.py` on `prometheus-client`. prometheus-fastapi-instrumentator is removed.
2. **The contract stays.** The five metrics keep their names, types, help texts, label names and buckets:

   | Metric | Labels |
   |---|---|
   | `http_requests_total` | `method`, `status`, `handler` |
   | `http_request_size_bytes` | `handler` |
   | `http_response_size_bytes` | `handler` |
   | `http_request_duration_highr_seconds` | none |
   | `http_request_duration_seconds` | `method`, `handler` |

   A test pins them.
3. **`handler` is the template FastAPI's routing has already chosen.** `RouteTemplates` builds two maps at start through the public `iter_route_contexts`: route object → served template, endpoint → served template. A request only looks them up after routing, in O(1). Prefixes of `include_router`, nested routers and mounts are supported. The start is refused when the scope cannot name one template: one route object or endpoint served under two templates, or an unknown kind of route.
4. **Label values come from closed sets.**
   - `handler` is a served template or `none`.
   - `method` is one of the RFC 9110 methods or QUERY; anything else is `_OTHER`.
   - `status` is `1xx`–`5xx`; a status outside 100–599 counts as `5xx`.
5. **Each request is recorded exactly once**, after its response or when its task is cancelled. Status 500 is recorded when no response was sent. Size comes from `Content-Length`, 0 when the header is absent or malformed, and recording never raises.

## Amendment (2026-10-13, F1 audit OD-3)

Decision 2 kept the instrumentator's names for the draft's dashboards and alerts. v2 has none yet (F5 is to come), so the owner chose the OpenTelemetry semantic conventions for HTTP servers instead: off-the-shelf Grafana dashboards and FastAPI's native metrics speak them. The mechanism — the boundary, `RouteTemplates`, closed label sets, one record per request — does not change.

1. **One metric**, as the OpenTelemetry SDK's Prometheus exporter names `http.server.request.duration`:

   | Metric | Type | Labels |
   |---|---|---|
   | `http_server_request_duration_seconds` | histogram, the conventions' advisory buckets 5 ms … 10 s | `http_request_method`, `http_route`, `http_response_status_code`, `url_scheme`, `error_type` |

   Rate and errors are its `_count`; the count without labels replaces `http_request_duration_highr_seconds`. Help text "Duration of HTTP server requests."; `tests/core/web/test_http_metrics.py` pins name, type, help, labels and buckets.
2. **Label values, still closed:**
   - `http_route`: a served template; empty when nothing matched (an absent attribute is an empty label in Prometheus).
   - `http_request_method`: an RFC 9110 method or QUERY, else `_OTHER`.
   - `http_response_status_code`: the code sent, a bounded set the application chooses; a status outside 100–599 counts as `500`; empty when no response started (a cancelled task, an app that sent nothing). Full codes replace the class: a series exists only for a code a route really answered, so a route adds a few series, not a hundred.
   - `url_scheme`: `https` or `http`; any other scope value counts as `http`.
   - `error_type`: the code of a 5xx response, `_OTHER` when no response started, else empty, as the conventions define it for HTTP.
3. **The body-size metrics are dropped.** `http.server.request.body.size` and `http.server.response.body.size` are opt-in in the conventions, which give them no buckets; no SLO, dashboard or alert of §16 reads them, and they would triple the series. Upload sizes are bounded by the presigned uploads, not by API bodies. Restoring them is additive.
4. **Series — the cost of this choice.** Per process: routes that answer × the codes each answers × 17 samples (15 buckets, sum, count). Upper bound with every one of 600 templates answering two codes over one scheme behind the edge: ≈ 20 400 series per API process, against ≈ 7 200 for the instrumentator's five metrics on the same table — about three times more. For three API processes, scraped every 30 s at ≈ 1.3 bytes a sample, that is ≈ 0.23 GB a day, ≈ 7 GB over the 30 days of §16.1, inside the 20 GB cap of §16.7. Real traffic touches far fewer templates; F5 measures it.

The scheduler loops follow OpenTelemetry's naming rules as well: `shosai_loop_interval_seconds`, `shosai_loop_last_success_timestamp_seconds`, and `shosai_loop_iteration_duration_seconds{shosai_loop_name, error_type}`, whose `error_type` (the exception's class, empty on success) replaces the failure counter (`core/runtime/loops.py`).

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep the instrumentator | 258 µs of CPU per request, raw paths and methods in labels, private-API coupling to FastAPI |
| Configure it differently | `should_ignore_untemplated` and `excluded_handlers` do not cover the trailing-slash branch or the method; the second match is its design |
| FastAPI's native OpenTelemetry metrics through a Prometheus exporter | It reads the routing result correctly, but every name and label changes (`http_server_request_duration_seconds`, `http_route`, full status codes), and it adds the metrics SDK and an exporter. The owner required the existing contract |
| Read FastAPI's private `scope["fastapi"]["effective_route_context"]` | It resolves every layout in one line, but it is the same private coupling that broke the draft |
| Read `http.route` from the server span | Metrics would depend on tracing being on and the span recording |

## Consequences

- In the same benchmark the metrics cost 4.6 µs of CPU per request (template lookup 0.1 µs, header scans 0.4 µs, `observe` 3.8 µs). Under open load, p99 and event-loop lag are indistinguishable from the boundary without metrics.
- About 210 lines of own code (`http_metrics.py`, `route_templates.py`) and one call site. Covered by 64 tests, including a Hypothesis property over arbitrary paths, methods, queries and `Content-Length` values, and a check that the shell adds no `matches()` call to FastAPI's routing.
- One dependency fewer.
- Values that change on purpose against the instrumentator:
  - a method outside the closed set, a lower-case one included, becomes `_OTHER`;
  - a trailing-slash redirect counts as `none`, not by its path;
  - a CORS preflight answered before routing counts as `none`;
  - a status outside 100–599 counts as `5xx`, not as `9xx` or `0xx`;
  - the last-resort 500 counts the size it sent instead of 0;
  - a malformed `Content-Length` counts as size 0, and the request keeps all five metrics.
- Exemplars (metric → trace, §16.1) can be added later at the one call site that already runs inside the request's server span; F5 decides.

## Limits and maintenance obligations

- **FastAPI and Starlette upgrades.** `RouteTemplates` relies on three behaviours of FastAPI 0.142:
  - `iter_route_contexts` returns each served route with its original object and full path;
  - `scope["route"]` is the declared `APIRoute`;
  - a plain Starlette route and an opaque mount leave only `scope["endpoint"]`.

  `tests/core/web/test_route_templates.py` checks all of them, including agreement with the `http.route` FastAPI itself traces. An upgrade that changes them fails CI before it reaches production. The upgrade review reruns that suite deliberately.
- **One router instance is included once.** A slice that needs the same handlers under two prefixes builds its router twice (routers are built by functions, F1 §3.1). The start error names both templates.
- **New kinds of routes** (`Host`, custom `BaseRoute` subclasses) stop the start until this module learns them, with a test.
- **Not covered:**
  - routes of `app.frontend()` are not listed by FastAPI and count as `none`, as with the instrumentator; S17 and F2 decide if the public site needs its own metrics;
  - WebSocket traffic is outside the HTTP metrics, as before; S05 owns its metrics.
- **The contract is a public interface.** Changing a name, a label, a help text or a bucket is a contract change for the dashboards and alerts of F5 and needs its own decision. The values of "Consequences" that compare with the instrumentator describe the original decision; the amendment above governs the names.

## Revisit when

- FastAPI publishes the effective route template of a request (then `RouteTemplates` reads it and the maps go).
- FastAPI's native metrics can be exported to Prometheus without the second route match and without labels from user input; then they replace this module under the same names.
