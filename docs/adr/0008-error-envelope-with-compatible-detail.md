# ADR 0008 — One error envelope with a compatible `detail`

- **Status:** accepted by the owner on 2026-10-01 (F1 planning, decision F1-D1).
- **Package:** F1, backend foundation; applied by every slice.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §10 ("one error envelope everywhere"), §16.2; [CLAUDE.md](../../.claude/CLAUDE.md) "Undecided", "Language"; [contracts/README.md](../../contracts/README.md) "Rules that no schema can express"; [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

The architecture requires one error envelope and a `request_id` in every error returned to a client, but does not define the shape.

The draft answers errors in three shapes:

| Case | Body |
|---|---|
| `HTTPException`, validation (422) | FastAPI default `{"detail": …}`; `detail` is a code string, a sentence, an object `{code, message}` or, for 422, a list that echoes the submitted `input` |
| Domain errors, unhandled 500, device-key 401 | `{"error": {"code", "message", "details"}}` |
| slowapi 429 | `{"error": "Rate limit exceeded: …"}` |

No body carries `request_id`. The `X-Request-ID` header is set by a middleware that sits inside Starlette's error handler, so an unhandled 500 most likely leaves without it.

What the shipped clients read (D1, `contracts/draft/consumers.json`):

- macOS 1.4.5 and Windows 1.4.5 read only the top-level `detail`. Its type is fixed per route: a string on sign-in (the literal `email_not_verified` on 403 is load-bearing), an object with `code` on voice translation, either on audio upload.
- Status codes are load-bearing: 401, 402, 403, 404, 409, 413, 422, 429. An unknown `/v1/...` path must answer 404 with JSON.
- Nobody reads `error`, `request_id` or `X-Request-ID`. The web frontend maps `detail` to the i18n key `errors:<code>`; it is rewritten in v2.

## Decision

1. **Every error response of the HTTP API has one body**, including framework errors (unknown path, method not allowed, validation) and unhandled exceptions:

   ```json
   {
     "error": {
       "code": "email_not_verified",
       "request_id": "0199a3c2e7f84b1c9d2e5f60718293a4",
       "params": {"retry_after_seconds": 30},
       "fields": [{"loc": ["body", "email"], "type": "value_error"}]
     },
     "detail": "email_not_verified"
   }
   ```

   - `error.code` — a stable snake_case machine code. Clients turn it into text through i18n; the server sends no user-facing sentence (CLAUDE.md "Language").
   - `error.request_id` — equal to the `X-Request-ID` response header.
   - `error.params` — optional values for the client's message: numbers, codes and ids, never personal data.
   - `error.fields` — only on 422: location and error type of each invalid field. The submitted value is never echoed.
   - `detail` — the compatibility field for shipped clients. By default it equals `error.code`. An error raised on a route whose draft contract (D1) has another shape declares that shape: an object `{"code": …}` (voice translation, audio upload) or the draft's exact string (sign-in). New routes use the default.

2. **`X-Request-ID` is on every response, including 500.** An incoming value is kept when it matches `^[A-Za-z0-9._-]{1,64}$`; otherwise the server generates one (UUIDv7, 32 hex digits). The middleware that sets it is the outermost one and renders the 500 envelope itself, so no response escapes without it.
3. **Content type stays `application/json`.**
4. **Status mapping is fixed in one place:** unknown path → 404 `not_found`; method not allowed → 405 `method_not_allowed`; validation → 422 `validation_error`; rate limit → 429 `rate_limited` with `Retry-After` and `params.retry_after_seconds`; unhandled → 500 `internal_error`, logged once with method, route template, `request_id` and stack, with nothing internal in the body.
5. **Domain code raises a framework-free error type** carrying the code, the status, optional params and the optional compatibility `detail`. The web layer renders it; domain code never builds response bodies.
6. **OpenAPI documents the envelope** as one `ErrorResponse` schema for every declared error status.
7. **WebSocket errors are out of scope:** they are frames and close codes owned by S05.

## Consequences

- One renderer and one set of handlers in `core`; every slice raises errors and never formats them.
- F2 reads `error.code`, keeps the draft's texts through `errors:<code>`, and shows `request_id` for support (§16.2).
- Each slice that owns a `native` route tests the `detail` shape of its errors against the draft; the D1 harness does not compare error bodies.
- The 422 body no longer echoes input, which removes a path for passwords and tokens to reach the client or logs.
- Dropping `detail` later is itself a contract change and needs the supported clients to read `error`.

## Revisit when

- No supported client reads `detail` any more.
- A client needs server-localised messages: add `error.message` additively.
