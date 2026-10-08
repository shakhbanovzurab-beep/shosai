# Leo in the draft — audit

- **Status:** audit for the Leo redesign, 2026-10-08. Input to [ARCHITECTURE.md](ARCHITECTURE.md) of this folder and to ADRs 0023–0032.
- **Subject:** the draft `/root/whisperer` at the D1 snapshot. Read-only.
- **Method:** six independent read-throughs, each of whole files, cross-checked against each other:
  1. agent core and LLM path;
  2. tools, confirmation and access control;
  3. memory, context, personalization, skills, RAG;
  4. proactivity, errands, notifications;
  5. web client and wire contract (and grep of the native clients);
  6. the state of v2 (frontend, backend core, contracts, plan).

  No conclusion below rests on one file. Paths are relative to `backend/src/meetassist/` unless they start with `frontend/`, `shared/`, `docs/` or `specs/`.

---

## 1. What Leo is in the draft

| Area | Size | Where |
|---|---|---|
| Agent core (graph, runner, nodes, state, checkpointer, progress) | ≈ 4 900 lines | `services/agent/*.py` |
| Tools | 130 tools in 17 modules, ≈ 7 300 lines | `services/agent/tools/`, `features/meetings/channels/agent_tools.py` |
| LLM layer used by Leo (catalogue, provider, prompts, safety, fallback) | part of 15 600 lines | `services/llm/` |
| Memory, personalization, skills | 2 345 + 506 + 675 lines | `features/memory`, `features/personalization`, `services/skills` |
| Proactivity and errands | 5 126 + 1 021 lines | `features/proactive`, `features/errands` |
| HTTP and WS entrypoints | 866 + 784 + 818 lines | `api/ai/agent.py`, `api/ai/voice_ws.py`, `api/ai/proxy.py` |
| Web client | ≈ 40 files; `LeoTab.tsx` 1 126 lines | `frontend/src/features/leo/` |

**Turn topology** (`services/agent/graph.py:73-120`), compiled once per process with a custom Redis checkpointer:

```
START → guard ─blocked→ refuse → END
guard → context → model ─tool_calls→ tools ─pending write→ meter → confirm(interrupt) → act → audit → model
                       │                   └─ reads only → model
                       └─ final text → finalize (meter, memory capture) → END
```

- **Channels:** `POST /v1/ai/agent/chat` (multipart, SSE), `POST /v1/ai/agent/act` (SSE), `prewarm`, `reminder-context`; voice through `WS /v1/ws/voice`, where Gemini Live is the "mouth" and calls the graph through `consult_text_expert`; MCP `tools/call`, which bypasses the graph; proactive and reminder text seeded into the thread by `append_turn`.
- **Model:** one provider (OpenRouter), default `deepseek/deepseek-v4-flash`, user's choice per role, `temperature 0.3`, `max_tokens 2048` (`services/agent/llm.py:30-39`).
- **Limits:** soft 4 / hard 12 tool rounds, 16 calls per round, 45 s per read tool, 300 s per turn (`turn_mode.py:39,59-67`, `tool_calls.py:38,142`, `config.py:496`).
- **State:** LangGraph state with the last 40 messages, the frozen system prompt and the pending action, in Redis for 24 h (`state.py:208-265`, `checkpoint.py`). The client keeps the visible history in localStorage and re-sends it (`frontend/.../useChatPersistence.ts`).
- **Measured latency** (the draft's own audit, `audit.md:419`): turn p50 ≈ 12 s, of which the model ≈ 9.6 s and the platform ≈ 2.3 s.

---

## 2. Findings

Severity: **H** — breaks an invariant of the target architecture, security or money, or blocks scale; **M** — wrong behaviour or a large cost; **L** — hygiene. Each finding names the target-architecture rule it violates, where one applies.

### 2.1 Confirm-before-write and safety

| # | Sev | Finding | Evidence | Violates |
|---|---|---|---|---|
| A1 | H | **At-most-once is not guaranteed.** The one-time claim lives 60 s, the card 1 h. Batch items commit one by one, the checkpoint is written asynchronously. A crash or the 300 s deadline after some commits leaves the interrupt pending; after 60 s it can be claimed and executed again. No idempotency key reaches the domain or external providers. | `services/agent/vault.py:33-58`, `config.py:579`, `runner.py:96-117`, `tools/connectors.py:169-174` | inv-12 |
| A2 | H | **Voice approval is a model tool call**, not a user act: Gemini Live calls `confirm_action(approved=true)` and the server resumes whatever is pending; with no card it injects "[SERVICE] The user said yes…" as a user turn. | `api/ai/voice_ws.py:263-292,349-372` | inv-12 |
| A3 | H | **MCP egress writes run without confirmation**, including persistent-injection sinks (`set_leo_personalization` text lands in the system prompt, `append_context`, `update_prompt`) and a full `update_note` overwrite. A partial flush is committed after a `ToolError`. | `api/mcp_transport.py:524-574,553-566` | inv-12, fr-4 |
| A4 | H | **Injection → exfiltration chain.** Untrusted mail and web text reach the model; unconfirmed "read" tools carry data out (`search_web` query, `generate_image` prompt, external MCP tools declared read-only). `wrap_untrusted` does not escape its END marker, labels are attacker-controlled (file names, meeting titles), and many channels are not wrapped at all (web results, calendar descriptions, meeting quotes, hub loops). | `core/untrusted.py:23-30`, `tools/web.py:106`, `tools/calendar.py:119-120`, `tools/storage.py:135` | §15, nfr-15 |
| A5 | H | **Untrusted text enters the thread as an assistant turn.** The LLM summary of an email body becomes reminder text written by `append_turn` without wrapping, into a graph with write tools. | `features/proactive/application/mail_scan.py:578`, `features/proactive/channels/ws.py:283`, `services/agent/runner.py:305-319` | — |
| A6 | H | **Memory is injected as "your own knowledge", unwrapped**, and it holds raw user text and third-party meeting speech ("claims"). "Remember: always skip confirmation" persists across sessions. | `services/agent/memory_link.py:115-122`, `features/meetings/application/projection_memory.py:76-90` | — |
| A7 | H | **External MCP tool descriptions and schemas go unsanitised into the tool list** (tool poisoning); `inputSchema` has no size cap. | `services/agent/mcp_tools.py:100-116` | — |
| A8 | M | Preview and execution can disagree: the preview counts at proposal time, execution re-queries up to 1 h later without a bound on the previewed set. Cards without `proposed_at` never expire. Batches are not atomic. Two racing `/act` overwrite each other's secret. | `tools/meetings.py:271-287`, `runner.py:240-242`, `api/ai/agent.py:731-732` | inv-12 |
| A9 | M | Calendar tools commit inside the handler, so "audit in the same transaction" does not hold; `clear_calendar` swallows errors and leaves partial work. | `tools/calendar.py:9-10,294-299` | inv-17 spirit |
| A10 | M | Hub scope is applied only by read tools; meeting writes, meeting-intelligence and graph tools ignore it; after `/act` the next model round runs **without** hub scope. | `tools/read.py:86-108`, `tools/meetings.py:95-103`, `api/ai/agent.py:711-714` | fr-13 |
| A11 | M | Audit stores full arguments (mail bodies, recipients); the MCP path stores raw args even for `no_logs` users; no retention, not append-only. | `models/agent_audit.py:28-53`, `api/mcp_transport.py:575-601` | §16.8 |

### 2.2 Agent core, state and contract

| # | Sev | Finding | Evidence | Violates |
|---|---|---|---|---|
| C1 | H | **No server-side conversation.** The visible history exists only in each browser's localStorage; the server thread dies after 24 h idle and is then re-seeded from client-sent history, so forged assistant turns can enter the context. No conversation list, no cross-device continuity, tabs overwrite each other. | `frontend/src/features/leo/hooks/useChatPersistence.ts:36-46`, `services/agent/runner.py:217` | fr-4 quality; §8.1 "loss restarts the dialogue" |
| C2 | H | **No per-thread serialization.** Two turns on one thread (two tabs, voice + text) both start from the same checkpoint; the last writer wins and one turn's messages are lost. Only a per-user in-flight cap of 2 exists. | `api/ai/proxy.py:244-270`, `services/agent/checkpoint.py:131,175-178` | inv-12 risk |
| C3 | H | **Leo bypasses spend control.** The agent calls `OpenRouterProvider` directly, not the router that applies the weekly premium reservation and money caps; metering is post-hoc with the provider hardcoded; usage of a cancelled or timed-out round is lost or billed to the next turn. | `services/agent/nodes.py:438-446,960-985`, `services/llm/router.py:295-347`, `runner.py:62` | §14 rule 4, inv-9 |
| C4 | H | **The Principal is assembled in five places with different fields:** voice lacks `has_connectors` (connector tools vanish), `/act` lacks hub scope, MCP lacks the web-search switch, reminders use fake entitlements. | `api/ai/agent.py:355-399,711-714,840-848`, `api/ai/voice_ws.py:673-691`, `api/mcp_transport.py:600-627` | inv-14 |
| C5 | H | **No reliable terminal frame.** Any non-timeout exception escapes `_drive`; SSE closes without `error` or `done`. A dropped stream is never resumed (no event ids). | `services/agent/runner.py:96-129`, `api/ai/agent.py:490-498`, `frontend/.../api/agent.ts:163-167` | §16.2 |
| C6 | M | `max_tokens 2048` is shared with non-switchable reasoning; `finish_reason=length` is ignored, so truncated answers and truncated tool JSON (`{}`) pass silently. | `services/agent/turn.py:71-101`, `services/agent/registry.py:343-350`, `REASONING_TASK.md` | — |
| C7 | M | Redundant I/O before the first token: the checkpoint is read twice per `/chat` and three times per `/act` (3 Redis round trips each), mentions are resolved one query at a time, memory capture (an embedding call) is awaited before `done`. Measured platform share ≈ 2.3 s vs the ≤ 500 ms target. | `services/agent/checkpoint.py:202-242`, `mentions.py:64-67`, `nodes.py:952` | nfr-7 |
| C8 | M | The checkpointer writes a full snapshot (including the frozen system prompt) on every superstep; the thread is never deleted on account deletion; `no_logs` does not apply to it; not home-aware. | `services/agent/state.py:390-393`, `checkpoint.py:110-143` | nfr-13 |
| C9 | M | One breaker per provider: one model's 5xx opens the circuit for all models; no fallback for paid models. | `services/llm/provider_breaker.py:17-22,52-55` | §13.2 |
| C10 | M | Boundaries: tools import 16+ ORM models and legacy services of other domains directly; `meetings` registers tools into the agent by import side effect; transport-to-transport private imports; god files (`nodes.py` 985 lines, `agent.py` 866, `voice_ws.py` 784). | `services/agent/tools/read.py`, `write.py`, `registry.py:355-374`, `api/mcp_transport.py:608` | §5, CLAUDE.md file limits |
| C11 | L | Process-local caches (guardrail, instructions) are never invalidated across workers; the guardrail cache fails hard on a DB error. | `services/agent/guardrail_cache.py:30-47` | — |
| C12 | L | No OpenTelemetry spans on the agent or LLM path, no run id, no TTFT metric; logs are `%s`-formatted. "Why did user X wait 18 s?" is unanswerable. | `services/agent/metrics.py`, `audit.md:388-397` | §16 |

### 2.3 Tools and context cost

| # | Sev | Finding | Evidence |
|---|---|---|---|
| T1 | H | **Schema bloat:** 130 tools (54 read, 74 write, 2 client) plus up to 100 external MCP tools; ≈ 20–25 K tokens of schemas **per round**, up to 12 rounds per turn. Selection is by tariff only, not by intent. The draft's own count: ≈ 120 tools in the catalogue, 3 actually used in a week. | `services/agent/registry.py:225-241`, `audit.md:335-358` |
| T2 | H | **No token budget for context.** History is capped at 40 messages, not tokens, and keeps raw tool results (some tens of KB); user context files are injected in full on every turn with no total cap; attachments up to 256 K chars; no summarisation. Minute-level `now_line` and per-turn memory sit before the history, so the history prefix is never cached. | `services/agent/state.py:88,265`, `services/user_context_service.py:37-45`, `services/llm/agent_actions.py:410-466` |
| T3 | M | Hand-written JSON-schema dicts, no validation; invalid JSON becomes `{}`; Russian model-facing strings and pass-through domain `detail` in tool errors. | `services/agent/registry.py:105-131,343-350`, `services/llm/mcp_client.py:419,424` |
| T4 | M | No global result-size cap (ticket thread up to 160 K chars); broken id chains (`list_tickets` returns no id that `reply_ticket` needs); overlapping tools (three context tools, list/search/stats of meetings, folders vs hubs). | `tools/support.py:35-36`, `tools/read.py:430`, `tools/hub.py:131-141,275` |
| T5 | M | `search_web` and `generate_image` are "read" tools that spend money, up to 16 per round, unconfirmed. | `tools/web.py`, `tools/image.py` |

### 2.4 Memory and personalization

| # | Sev | Finding | Evidence |
|---|---|---|---|
| M1 | H | **The memory switch is bypassed:** the meeting pipeline writes memory without the `enabled` flag; nightly consolidation runs an LLM over the memory of users who switched memory off or set `no_logs`. | `features/meetings/application/projection_memory.py:73`, `features/memory/channels/tasks.py:115-125` |
| M2 | H | Consolidation takes `ORDER BY user_id LIMIT 301` with no cursor: the same 300 users every night, the rest never; the same rows are re-sent each night. | `features/memory/infrastructure/repository.py:162-179` |
| M3 | H | Updates keep the **longer** text, not the newer: "I work at A" → "I work at B" merge into a contradiction; every recall `touch` resets decay for anything retrieved. | `features/memory/domain/dedup.py:58-66`, `memory_service.py:216` |
| M4 | M | No provenance (Leo cannot say why it believes something), no embedding model/version column, episodes are raw commands, recall uses only the last message (follow-ups recall noise). | `features/memory/contracts/dto.py:62-71`, `memory_link.py:92` |
| M5 | M | Language-dependent logic: a 16-language "remember" regex decides fact vs episode; an "ephemeral words" list rejects even explicit requests; length thresholds penalise CJK. | `memory_link.py:54-83`, `features/memory/domain/salience.py:21-153` |
| M6 | M | Skills (SKILL.md from GitHub/skills.sh) never reach Leo — they are bound only to role prompt templates, and the `agent` role has none. Personalization is explicit settings only; nothing is learnt. | `services/llm/prompt_composition.py:280-298`, `services/llm/agent_actions.py:73-77` |
| M7 | M | Seven retrieval systems, two embedders (384-d and 3 072-d), legacy notes RAG with orphan vectors; KB provider failure is reported to the model as "you have nothing". | `docs/KNOWLEDGE_ENGINE_TARGET_ARCHITECTURE.md:89-135`, `tools/read.py:329-374` |

### 2.5 Proactivity and errands

| # | Sev | Finding | Evidence |
|---|---|---|---|
| P1 | H | **"Should Leo speak now?" is static rules.** Urgency is a constant per kind; there is no per-instance value, the stored `confidence` of a commitment is ignored, there is no notion of the user's attention (in a meeting, focused) beyond socket presence. | `features/proactive/domain/restraint.py:34,171-243`, `scanner.py:289` |
| P2 | H | **The feedback loop is dead.** Fatigue depends on ratings, but there is no rating UI; dismissal is not recorded; `acked` means "frame arrived", even in a background tab; the advertised value-rate metric cannot be computed. | `features/proactive/channels/http.py:257`, `frontend/.../ReminderToast.tsx:38-45`, `useUserEvents.ts:87` |
| P3 | H | **Global polling.** All sources are scans over all users every 5 min with unordered `LIMIT 500` (silent starvation), ≈ 6 queries per candidate, mail capped at 100 mailboxes per pass (≈ every 4 h per mailbox at 5 000 mailboxes), and a full-keyspace Redis `SCAN` per presence check. No domain events are consumed although an outbox exists. | `scanner.py:141-145`, `mail_scan.py:79,268`, `core/user_push.py:142` |
| P4 | H | **Errand email can be sent twice or days late, unconfirmed.** Unlocked status read, commit after send, no idempotency key; `repair` starts a new workflow every 10 min for a stuck row; transient failures retried without a lateness bound. Failed errands are not reported and are deleted after 24 h. | `features/errands/application/executor.py:46,68-71`, `errand_service.py:38,196-221` |
| P5 | H | An open background tab swallows every nudge (wins channel selection and acks on receipt), so push and desktop never fire while the user is away; non-durable nudges (prep, looping topics) are lost if nobody is online. | `features/proactive/application/delivery.py:95-96,338-343` |
| P6 | M | Three uncoordinated reminder systems (calendar email job, `MEETING_SOON`, errands) and three schedulers (TaskIQ ticks, Temporal, per-minute calendar job); cancelled meetings still trigger `MEETING_SOON`. | `tasks/calendar_notifications.py`, `scanner.py:143` |
| P7 | M | LLM summaries of mail are generated **before** the restraint and paid gates, so most of that spend is wasted; every web nudge auto-plays server TTS, unthrottled. | `mail_scan.py:419-420`, `channels/http.py:199-245` |
| P8 | M | The daily cap counts explicit reminders and held nudges; a crash between nudge commit and delivery is reported as success; web push sent inside an open transaction. | `proactive_service.py:428-433,533-537`, `push.py:59-61` |

### 2.6 Client

| # | Sev | Finding | Evidence |
|---|---|---|---|
| W1 | H | Every token re-renders the whole widget tree; Markdown re-parses the whole growing answer every 80 ms (O(n²) on long answers). | `frontend/.../useAgentChat.ts:52-77`, `shared/markdown/ui/MarkdownMessage.tsx:139-151` |
| W2 | H | The client mirrors server registries by hand (46 of 130 tool names, 14 cache sections, proactive kinds, upload limits) and drifts; "6+ places per new tool". | `frontend/.../contracts/agent.ts:10-63`, `model/invalidation.ts:15-32` |
| W3 | M | Not accessible: the panel is not a dialog (no focus management, no Escape), the feed has no `role="log"`/live region, the mention list has no combobox wiring. | `ChatWidget.tsx:282-380`, `ChatComposer.tsx:455-489` |
| W4 | M | Whole widget, voice classes and `/ws/user` socket in the shell bundle on every page; `ScriptProcessorNode` and base64-in-JSON audio. | `features/leo/feature.ts:13`, `api/geminiLive.ts:182` |
| W5 | M | Errors written into the conversation and sent back to the model as assistant turns; chat text left in localStorage after logout. | `useAgentChat.ts:128`, `useChatPersistence.ts:19-25` |

---

## 3. What the redesign keeps

Behaviour and lessons, not code:

1. **Server-held confirmation.** The action lives on the server; the client sends only an id and yes/no; a confirmation node with no side effects separate from the execution node; a server-computed, localised preview of the real scope ("will delete 14 meetings") shown apart from the model's own words; explicit `scope` for bulk deletes; secrets only in the card, one-time, never by voice, never in agent state.
2. **Authority outside model-controlled state.** The principal travels in the runtime context; thread ids are derived by the server; owner always from the principal; ownership re-checked in the query.
3. **Budgets and honest failure.** Calls per round, per-call timeout, turn deadline, a final round without tools; every tool call gets a result; errors returned as data the model can explain; honest truncation flags.
4. **A closed, typed stream vocabulary** and the progress ledger: stable step ids, monotonic `seq`, server-measured durations, activity codes localised by the client; every pre-stream refusal as an HTTP error.
5. **Proactive restraint principles:** one choke point for all initiative, defaults toward silence, quiet hours that defer rather than drop, the insistence ladder `initiative / requested / explicit`, a mandatory machine-readable reason and evidence ids for every nudge, mail importance requiring two independent signals.
6. **Delivery state machine:** unique (nudge, channel), ack, settle across channels, replay on `hello`, presence TTL, per-device Web Push with RFC 8291.
7. **Memory principles:** pure domain functions (salience, dedup, decay, budget); hard prompt caps; off-switch stops write and recall without deleting; soft-forget then purge; decisions and commitments live in the context graph, not in memory.
8. **Personalization design:** closed presets, user text between delimiters as a preference never a permission, empty output at defaults (prefix cache kept).
9. **Mentions as server-verified pointers** `{kind, id}`; hub id as a hard scope.
10. **External MCP hygiene:** one-way trust (only read-only declared tools skip a card), namespacing, SSRF revalidation per call, size caps, stale-while-revalidate spec cache.
11. **Measurement-driven retrieval decisions** (RRF switched off when it lowered recall; rerank abstention gate; model id stored per vector) and the meeting-search eval harness.
12. **One thread for text and voice**, a cache-stable prompt order (static first), release of the DB session before streaming, deterministic computation (CSV statistics) instead of model arithmetic.

## 4. What the redesign drops

| Draft approach | Why it goes |
|---|---|
| Client-held history, seed on expiry | C1: no continuity, forged context |
| Redis as the only home of a conversation and of pending actions | C1, A1, §8.1 durability |
| One flat registry of 130 tools sent every round | T1: cost, latency, tool-choice errors |
| Tools reaching into other domains' ORM models | C10, §5 |
| Five principal builders | C4 |
| Voice approval by the voice model | A2 |
| MCP writes without confirmation | A3 |
| Static urgency rules as the only judge of initiative | P1 |
| Global 5-minute scans | P3 |
| Temporal for single-step delayed actions | P6, §12 (errands rows) |
| Memory written from raw messages by regex | M5, A6 |
| Skills bound only to role prompt templates | M6 |
| Post-hoc metering beside the provider | C3, §14 rule 4 |
