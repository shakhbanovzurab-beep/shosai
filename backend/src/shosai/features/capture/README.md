# capture

Leo's voice mode on the WS gateway: a Gemini Live conversation with the voice Charon, its exchanges written to the person's thread, its minutes counted against the plan. Decision: [ADR 0070](../../../../../docs/adr/0070-leo-voice-on-gemini-live.md); plan: [LEO-voice](../../../../../docs/plan/packages/LEO-voice.md). The desktop clients' live capture (`/v1/ws/realtime`, translation) joins the slice with its own package.

## `WS /v1/ws/voice`

Served on the `ws` role by core's `SocketGateway` (origin, capacity, `hello` within 5 s, close codes `4000 + status` with the error code as the reason, `server.shutdown` before the drain).

1. `hello` — `{type, v: 1, token, scope: {kind: personal} | {kind: workspace, workspace_id}, thread_id?, path?, locale?}` (`domain/voice.py`); a malformed one is 4400 `bad_hello`. Identity names the person (4401).
2. One conversation per person: a Valkey lock `capture.voice.<user>` held for the conversation and extended every minute (90 s TTL); a second one is 4409 `voice_busy`, Valkey down is 4503.
3. The month's minutes (billing's `MINUTES_ALLOWANCE`): used up is 4402 `minutes_exhausted`.
4. The agent's `VOICE_TURNS.open`: the thread, consent, voice mode and tokens — its refusals close with their status and code (`voice_mode_off` 4403, `thread_not_found` 4404, `token_limit` 4402, `consent_required` 4403).
5. Gemini Live (`CAPTURE_VOICE_MODEL`, `gemini-3.8-live`) through the AI port, expensive and interactive, with Leo's instruction, Charon, the page's tools and a 500 ms end of phrase; a refusal of the port closes with its status. The conversation's row is written, then `ready {session, thread_id, input_rate, output_rate}`.

The relay (`channels/voice_relay.py`) runs the cabinet's frames (PCM16 16 kHz to Gemini, `end`), Gemini's events and a watch together; the first to finish ends the conversation:

| Server frame | When |
|---|---|
| binary | Leo's speech, PCM16 24 kHz |
| `state {listening, thinking, speaking}` | on a change |
| `transcript {who: person, leo, text, final}` | each side's words of the exchange so far |
| `step {activity, status}`, `action.proposed {action_id}` | a tool call's steps and cards, through the agent |
| `interrupted` | the person spoke over Leo: the cabinet drops what it still plays |
| `ended {code}` | `ended`, `idle` (2 min without speech), `time_limit` (30 min), `minutes_exhausted` (closes 4402), `voice_unavailable` (Gemini lost, 4503), `server_shutdown` (1012) |

A tool call runs beside the loops through the agent (`VoiceConversation.call`); one Gemini cancels is cancelled; one the agent cannot answer gets a registered English error, so Gemini never waits. An exchange is recorded when Leo, having said something, ends its turn, or when the person interrupts it; what was said when the conversation ends is recorded as interrupted (`domain/exchanges.py`).

## Minutes

`capture_voice_sessions` (each home, personal by row-level security, monthly partitions keeping the current and the previous month): a row per conversation, its seconds written every minute and at the end with its end code. `VoiceMinutesCount` binds billing's `MEETING_MINUTES` beside notes' meetings, so voice minutes count against the plan's monthly minutes (BL-D3); every minute the conversation asks billing again and ends when none are left. The AI port meters the provider's cost minute by minute on its own (F6).

## Data, settings, metrics

The table is in the registry of a person's data (`application/account_data.py`): exported, erased and moved between homes with the person. `CAPTURE_VOICE_MODEL` — `.env.example` section 2. Metrics: `shosai_capture_voice_conversations_total{end}`, `shosai_capture_voice_conversation_seconds`, beside the gateway's `shosai_ws_*` for the route.
