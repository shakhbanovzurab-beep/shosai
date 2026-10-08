# ADR 0032 — `/v1/agent/*` with resumable SSE runs; native routes kept

- **Status:** proposed on 2026-10-08; awaits the owner.
- **Packages:** S09 (`agent`, `proactive`), F2 (cabinet client).
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §13.2; [Leo audit](../design/leo/AUDIT.md) C1, C5, W1, W2; ARCHITECTURE.md §10 contract rules, nfr-12; [ADR 0022](0022-new-web-design-replaces-draft-parity.md); D1 `contracts/draft/consumers.json`.

## Context

The draft's agent API is `POST /v1/ai/agent/chat`, multipart, returning SSE with the events `token`, `status`, `step`, `image`, `action`, `action_result`, `error` and `done`. Next to it are `POST /v1/ai/agent/act` and `prewarm` / `reminder-context`. Its problems:

- **No resume.** Streams have no event ids. A dropped stream loses the answer while the server finishes it (C5).
- **History from the client.** The client sends history, and there is no history or thread endpoint (C1).
- **Two shapes under one name.** `status` carries two payload shapes.
- **Images inside the stream.** They travel as base64 in the event.

The new cabinet's mock uses NDJSON over POST with `step_start`, `step_end`, `text`, `done` and `error`.

D1 classifies `/v1/ai/agent/*` and `/v1/ws/voice` as `web`: the Swift kit's Leo module reaches users only through the unshipped iOS app. These routes may therefore change together with the cabinet (ADR 0022). The `native` routes must stay: `/v1/ai/chat/stream`, `/v1/ai/vision/analyze`, the reminder `done` and errand `snooze` routes, and `/v1/ws/user` with `reminder.due` and `reminder.settled`.

## Decision

1. **Resources:**
   - threads per scope (`GET/POST /v1/agent/threads`, `GET/PATCH/DELETE …/{id}`, cursor-paginated `…/messages`);
   - turns (`POST /v1/agent/threads/{id}/turns` → `text/event-stream`, JSON body with `upload_ids` for attachments uploaded through presigned uploads, `Idempotency-Key` = client message id);
   - runs (`GET /v1/agent/runs/{id}/events` with `Last-Event-ID`, `POST …/cancel`);
   - actions (`GET /v1/agent/actions`, `POST …/{id}/approve` and `…/reject`);
   - suggestions (`GET /v1/agent/suggestions`, `POST …/{id}/feedback`);
   - settings, memory and skills under `/v1/agent/`.
2. **SSE through FastAPI's `EventSourceResponse`.** Every event has a monotonic `id`, and a heartbeat comment goes out every 15 s. The run's events are also appended to a Valkey stream (≤ 2 000 events, TTL 1 h), so any API process can serve a resume.
3. **Event vocabulary:**
   - `run.started`;
   - `step.started` / `step.completed` / `step.failed`, the ledger semantics kept from the draft;
   - `text.delta`;
   - `artifact`, a reference, never base64;
   - `client.action`;
   - `action.proposed`, `action.updated` (with `invalidates`);
   - `run.paused`, `run.completed`, `run.failed{code}`.

   A run always ends with exactly one terminal event. Unknown event types are ignored by clients (§10).
4. **Pre-stream refusals are HTTP errors** in the ADR 0008 envelope: 401, 402, 409 `thread_busy`, 413, 422, 429.
5. **Native routes unchanged.** New `/v1/ws/user` frames (`agent.suggestion`, `agent.action_updated`) are additive.
6. **Dropped** with the cabinet's move to the new API: `/v1/ai/agent/{chat,act,prewarm,reminder-context}` and the old memory, personalization and proactive settings routes. `/v1/proactive/feed*` was already `unused` (FM-5). `/v1/ws/voice` is redesigned by S05 on the agent port.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep `/v1/ai/agent/chat` and its events | no resume, client history, two-shape `status`, base64 images; the only shipped client using it is the web cabinet being replaced |
| NDJSON over POST (the new UI's mock) | no standard resume (`Last-Event-ID`), no heartbeat convention; the FastAPI skill's standard for streaming events is SSE |
| WebSocket for turns | stateful connections on the API role, a second protocol beside `/v1/ws/user`; turns are request-scoped and fit HTTP |
| `202 {run_id}` then a separate GET stream | one extra round trip on every turn (L-N2); resume already covers the reconnect case |

## Consequences

- **Reconnects are lossless** within an hour; after that the thread holds the answer.
- **The cabinet's Leo client is generated from OpenAPI.** Tool labels come from activity codes and cache invalidation from `invalidates`, which ends the hand-mirrored registries (audit W2).
- **The draft's SSE parser in the cabinet is not reused.** The new client implements the vocabulary above.
- **The snapshot test** of public routes and frame types (§10) gains these routes and events.

## Revisit when

- A native client adopts Leo, which then freezes this vocabulary as `native`.
- Proxies on a customer's network are found to buffer SSE in practice → add a WebSocket fallback on `/v1/ws/user`.
