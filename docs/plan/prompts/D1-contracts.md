# D1 — API and WebSocket contract baseline

Follow the common protocol in `docs/plan/prompts/README.md`.

## Goal

Capture the draft's external contract so every v2 slice can prove it is compatible. Native clients that are already shipped must keep working without an update (target architecture nfr-12), and their code is outside the rewrite, so this baseline is the only guard.

## Inputs

- Draft backend: `/root/whisperer/backend/src/meetassist/` — routers in `api/` and `features/*/`, WebSocket handlers.
- Draft frontend: `/root/whisperer/frontend/src/` — the API calls it makes.
- Native clients, **read only, to find what they call**: `/root/whisperer/macos-client`, `ios-client`, `linux-client`, `windows-client`, `pwa-app`, `shared/WhispererKit`. Do not change them.

## Work

1. Produce the draft's OpenAPI document. Prefer generating it from the draft application in a throwaway environment that uses no production configuration; if that is impossible, derive it from the routers and say how.
2. Catalogue every WebSocket endpoint: path, handshake and authentication, every frame type in both directions with its fields, protocol version handling, close codes.
3. List every HTTP endpoint and WebSocket frame used by each native client and by the web frontend, with file and line references.
4. Classify each endpoint: used by shipped native clients (must stay compatible), used by the web frontend only (may change together with the frontend), used by external integrations such as webhooks and MCP (must stay compatible), or unused.
5. Write a compatibility test harness in `contracts/` that a v2 slice can run against the v2 OpenAPI and WebSocket definitions to find missing or changed endpoints and frames. It is used by slices; it does not need v2 code to exist yet.

## Output

- `contracts/draft/openapi.json`, `contracts/draft/websocket.md`, `contracts/draft/consumers.md` (the classification).
- `contracts/README.md`: how slices use the baseline and the harness.

## Definition of done

- Every route in the draft is in the OpenAPI document or listed as excluded with a reason.
- Every endpoint and frame used by a native client is marked as must-stay-compatible.
- The harness runs and is documented.
- No production configuration or data was used.
