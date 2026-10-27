# Leo voice — package plan

The request: the owner's message of 2026-10-26 in the agent session — «В голосовом режиме должен быть голос Charon от Gemini», and the owner's choice the same day between three ways of doing it: **a live Gemini Live session** (chosen), speech synthesis of text answers, or waiting for `capture`.

- **Status:** written on 2026-10-26; **approved by the owner on 2026-10-27**: LV-D1…LV-D9 as written, voice minutes from the plan's monthly minutes (LV-D7), and the Leo architecture's Q-6 decided — reversible and compensable actions may be approved by voice (§8.4). Recorded in [ADR 0070](../../adr/0070-leo-voice-on-gemini-live.md).
- **Who decided what.** That voice mode is a live Gemini Live session with the voice Charon is **the owner's, of 2026-10-26**; LV-D1…LV-D9 were this plan's proposals and are **approved by the owner as written** (2026-10-27), and Q-6 is **the owner's** decision. The wire, the steps and the design of §3 are this plan's, derived from them.
- **Slice.** The voice assistant is `capture`'s (Leo architecture §15: agent provides `run_voice_turn`, `confirm_by_voice` to `capture`; agent plan §3.7). This package builds `capture`'s voice part and the WS gateway it needs, ahead of `capture`'s live transcription for the desktop clients, which keeps its own plan.
- **Supersedes** SLICE_MAP §2.4 "Voice mode: Browser Web Speech only; transcripts sent as messages; no server voice".
- **Philosophy check:** the person talks, Leo answers in a calm voice and can be interrupted; nothing is decided by voice that the screen should decide (§2, LV-D6). A conversation spoken is the same conversation as typed: one thread.

---

## 1. Facts this plan rests on

- **The provider port is ready.** `open_voice_session(context, model, VoiceSetup)` (F6 step 3b) opens a Gemini Live session on `gemini-3.8-live` (priced: text in $0.75, audio in $3.00, text out $4.50, audio out $12.00 per million tokens) with a prebuilt voice, tools, transcription of both sides, PCM16 16 kHz in and 24 kHz out, admission, slots, a breaker, minute rows and a reservation renewed every minute. No slice calls it yet. Its events lack two that voice needs: Gemini's `turnComplete` and `interrupted` are dropped by the adapter.
- **The WS gateway exists only as a role.** `ProcessRole.WS` serves `ws_routers`, but uvicorn runs with `ws="none"` ("the library and the frame protocol are chosen with S05"), there is no WebSocket authentication, no slot pool, no `server.shutdown`, and no route. The edge sends `/v1/ws/*` to the gateway (§4.3: 5 s handshake, 1013 when full).
- **A browser WebSocket cannot send `Authorization`.** The cabinet holds its access token in memory and sends it as a header.
- **Agent tools are tied to a text run.** `TurnRouting.offer` gives the same `ToolSchema`s `VoiceSetup` takes; reads run through `ReadTool.run` with a `ToolContext`; writes become cards through `ActionProposer`, which needs a run. `Channel` is `web`, `admin`; `ApprovedVia` is `web`, `inbox`.
- **The cabinet's voice mode** is the browser's Web Speech (recognition, then `chat.send`, then `speechSynthesis`); the cabinet has no WebSocket client and no audio capture or playback beyond a chime.
- **Cost.** Gemini bills 25 input-audio tokens a second sent and 25 output-audio tokens a second spoken: about $0.0045 a minute of listening and $0.018 a minute of Leo speaking, before text and tool tokens.

## 2. Decisions

| # | Question | Proposal | What follows |
|---|---|---|---|
| **LV-D1** | Where the session runs | **On the `ws` role, `WS /v1/ws/voice`, a `capture` route.** The server holds the Gemini session (ADR 0043 §8: the server meters what it sends and receives); the browser sends microphone audio and plays Leo's | WS gateway foundation in core (step 2); `features/capture` starts with its voice part |
| **LV-D2** | The wire | **JSON text frames for control, binary frames for audio.** Client: `hello {v: 1, token, scope, thread_id?}` first, then PCM16 16 kHz mono frames of 40 ms, `mute`, `end`. Server: `ready {session, thread_id, rates}`, PCM16 24 kHz frames, `state` (`listening`, `thinking`, `speaking`), `transcript {who, text, final}`, `interrupted`, `step` (a tool Leo runs), `action.proposed`, `ended {code}`, `server.shutdown` | Frame snapshot test (§10); the protocol version in `hello` |
| **LV-D3** | Authentication | **The access token in `hello`, within 5 s of the upgrade, checked by identity's `Authenticator`; the `Origin` must be the cabinet's.** No token in the URL (it would reach logs). Closed with 4401 on a bad token, 4403 on a foreign origin. A session ends when its sign-in session is revoked (`SessionsRevoked`) | identity's WS helper; the frontend's token is read at the start of voice mode |
| **LV-D4** | Model, voice, language | **`gemini-3.8-live`, voice Charon, end of a phrase after 500 ms of silence.** The instruction is Leo's voice prompt (English, registered with the prompts test): short spoken answers, no Markdown, answer in the language the person speaks unless Settings › Leo › response language says otherwise | A voice row in Settings › Leo later, if the owner wants a choice of voices |
| **LV-D5** | One thread | **A voice session belongs to the scope's current thread (a new one when there is none).** Each exchange — the person's phrase and Leo's answer, from Gemini's transcripts — is written at the turn's end as a user and an assistant message, with an `agent_runs` row of channel `voice` (both homes, migration) and the sources of the reads it made. The panel shows them when voice mode closes | agent's `VoiceTurns` port (step 4) |
| **LV-D6** | What Leo may do by voice | **Read with the same tools, switches and access policy as a text turn; a write becomes a card on the screen** ("I've prepared it — confirm on the screen"). **Q-6, decided by the owner on 2026-10-27:** a reversible or compensable write may then be approved by voice as §8.4 says (step 8); the rest stays on the screen | Cards appear in voice mode (step 6); voice approval in step 8 |
| **LV-D7** | Limits and money | **One voice session per person; at most 30 minutes; it ends after 2 minutes without speech.** The F6 meter reserves each minute. **Voice minutes count against the plan's monthly minutes (BL-D3), as in the draft** — a person with no minutes left gets "voice minutes are used up" and the text chat | billing's minutes meter takes `voice` minutes (step 5) |
| **LV-D8** | Audio in the browser | **Capture and playback in AudioWorklets**: the microphone with echo cancellation, noise suppression and gain control, resampled to 16 kHz; playback from a buffer at 24 kHz. **Interruption:** when Gemini reports `interrupted`, the buffer is dropped at once | The orb follows `state` and the microphone's level |
| **LV-D9** | When Live is unavailable | **No browser fallback.** Voice mode says why (no minutes, provider busy, offline) and offers the text chat; the Web Speech path is removed | One voice path to keep correct |

## 3. Design

### 3.1 Layout

- `core/web` and `core/runtime`: WebSocket support on the `ws` role (`websockets`, already pinned at 16.1.1 for google-genai), the WS boundary (request id, metrics by route and close code), a slot pool per process (Valkey "WS slots", §4.2) and per person, `server.shutdown` before a drain.
- `core/ai`: `LiveTurnEnd` and `LiveInterrupted` events from the Gemini adapter, with tests on the live double.
- `features/agent`: the `VoiceTurns` port (`contracts/voice.py`) — `open(principal, VoiceStart)` checks the thread, consent, voice mode and tokens as a text turn does and gives a `VoiceConversation`: the instruction and the page's tool schemas from the same routing (without `load_toolset` and `navigate`, which a fixed session cannot use), `call(...)` (the text turn's tool round: a read under the policy with its sources, or a card) and `record(VoiceExchange)` (the question, the answer and the run row). `Channel.VOICE` and the check constraint in both homes.
- `features/capture`: `WS /v1/ws/voice` — hello, admission (minutes, one session), the relay between the browser and `LiveSession`, tool calls to `VoiceTurns`, exchanges recorded at each turn end, limits, close codes (the gateway sends the refusal's error code as the close reason, so the cabinet tells `token_limit` from `minutes_exhausted`). Voice minutes: `capture_voice_sessions` in each home, seconds written every minute, read by billing through `MEETING_MINUTES`, which now takes several bindings (notes' meetings, capture's conversations). Details: [capture/README.md](../../../backend/src/shosai/features/capture/README.md).
- `frontend/src/features/leo`: the voice client (socket, worklets, buffer), voice mode on it, cards in voice mode, the thread refreshed when voice mode closes; MSW's WebSocket mock for `npm run dev`.

### 3.2 Not in this package

A choice of voices; the desktop clients' `/v1/ws/realtime` and voice translation (`capture`'s own plan); the native clients.

## 4. Steps

| # | Step | Skills | Done when |
|---|---|---|---|
| 1 | **Approval and records.** The owner approves §2; [ADR 0070](../../adr/0070-leo-voice-on-gemini-live.md); SLICE_MAP §2.4 and the agent plan's §3.7 point here; STATUS row; the Leo architecture's Q-6 marked decided | — | The plan is approved and the documents agree |
| 2 | **WS gateway foundation.** uvicorn WebSockets on `ws`; the gateway's sockets with metrics; hello authentication (LV-D3) as an identity helper; the process's slots; `server.shutdown` and the drain; the edge's `/v1/ws/` upgrade checked (one session per person comes with the voice session, step 5) | fastapi, python-doctor, resilience-failure | A test route on the gateway: authenticated, refused without a token or from a foreign origin, closed with `server.shutdown` on stop |
| 3 | **Live events.** `LiveTurnEnd` and `LiveInterrupted` from Gemini's `turnComplete` and `interrupted`; tool-call cancellation logged | fastapi, python-doctor | Live double scenarios cover both events |
| 4 | **Agent's `VoiceTurns`.** Voice setup from the scope's routing; reads with sources under the policy; writes as cards; exchanges written with `channel = voice` (migration in both homes) | fastapi, python-doctor, agent-architecture | Tests: a read in voice gives the same result and sources as in text; a write gives a card, never runs |
| 5 | **`WS /v1/ws/voice`.** Admission with minutes (billing meter) and one session per person (a Valkey lock held for the session's life); relay, states, transcripts, tool calls, exchanges at turn end; 30-minute and 2-minute limits; close codes; frame snapshot | fastapi, python-doctor, api-design, resilience-failure | An end-to-end test on the live double: hello → speech → tool → spoken answer → two messages in the thread, minutes metered |
| 6 | **Cabinet: voice mode on the server.** Socket client, capture and playback worklets, interruption, the orb by `state` and level, cards in voice mode, thread refreshed on close; the Web Speech path removed; MSW WebSocket mock | the four frontend skills, react-doctor | Voice mode on the local API with the live double; unit tests of frames and resampling |
| 7 | **Staging with Gemini.** Charon on staging with the real key: latency to first sound, interruption, a tool round, cost per minute against the meter; findings fixed | — | The owner hears Charon on staging |
| 8 | **Voice confirmation** (Q-6, the owner's). *Done on the agent's and capture's side 2026-10-27 (`VOICE_APPROVAL_JUDGE`, fail-closed); the judge needs the owner's decision on the Decision Layer's "never grants a permission" invariant — see STATUS.* §8.4: the read-back of the server preview, `noul`'s judgement of the next phrase in 16 languages, `confirm(action_id)`, `approved_via = voice` (both homes); reversible and compensable actions only, never when tainted or screen-only | fastapi, python-doctor, agent-architecture | A2 regressions covered by tests |

## 5. Risks

- **Latency.** Gemini Live's first sound comes in under a second in Google's region; the plane is in the EU, the RU home's people cross the border only with consent (admission refuses otherwise). Measured in step 7.
- **Echo.** Without headphones the microphone hears Leo; echo cancellation in the browser and Gemini's own activity detection handle most rooms, and interruption keeps a false start short.
- **Cost.** A 30-minute session where Leo speaks half the time costs about $0.35; the minutes quota and the one-session rule bound it.
