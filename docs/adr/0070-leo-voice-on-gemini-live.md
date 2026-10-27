# ADR 0070 — Leo's voice mode is a Gemini Live session with the voice Charon

- **Status:** accepted by the owner: the way (a live Gemini Live session, voice Charon) on 2026-10-26; the [package plan](../plan/packages/LEO-voice.md) with LV-D1…LV-D9 as written, voice minutes from the plan's monthly minutes, and the Leo architecture's Q-6 on 2026-10-27.
- **Packages:** [LEO-voice](../plan/packages/LEO-voice.md) (`capture`'s voice part, the WS gateway's foundation); `agent` (`VoiceTurns`, channel `voice`, `approved_via = voice`); `billing` (voice minutes); identity (WebSocket authentication); core (WebSockets on the `ws` role, live events).
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2–§4.3, §10; [Leo architecture](../design/leo/ARCHITECTURE.md) §8.4, §15, §17 Q-6; [ADR 0043](0043-speech-providers-by-task.md) §4, §8; [agent plan](../plan/slices/agent.md) §3.7; SLICE_MAP §2.4.

## Context

- The cabinet's voice mode listens and speaks with the browser's Web Speech: robotic voices that differ by browser and language, no interruption, and a recognition the server never sees. SLICE_MAP §2.4 recorded it as "no server voice".
- The owner asked on 2026-10-26 for Gemini's voice Charon in voice mode and chose, among a live session, speech synthesis of text answers and waiting for `capture`, the live session.
- F6 step 3b built `open_voice_session` (Gemini Live, `gemini-3.8-live`, prebuilt voices, tools, both transcripts, minute rows), but nothing calls it; the WS gateway is a process role with WebSockets off.

## Decision

1. **Voice mode is a Gemini Live session the server holds** (LV-D1): `WS /v1/ws/voice` on the `ws` role, a `capture` route; the browser streams microphone audio (PCM16 16 kHz) and plays Leo's (PCM16 24 kHz). Model `gemini-3.8-live`, voice **Charon**, end of a phrase after 500 ms of silence (LV-D4).
2. **The wire** (LV-D2): JSON text frames for control, binary frames for audio; `hello` first with the protocol version, the access token and the scope; `ready`, `state`, `transcript`, `interrupted`, `step`, `action.proposed`, `ended`, `server.shutdown` from the server.
3. **Authentication in `hello`** (LV-D3): the access token within 5 s of the upgrade, checked by identity's `Authenticator`; the cabinet's `Origin` only; never a token in the URL.
4. **One thread for text and voice** (LV-D5): each exchange is written at its turn's end — the person's phrase and Leo's answer from Gemini's transcripts — with an `agent_runs` row of channel `voice` and the sources of its reads.
5. **Reads like a text turn, writes as cards** (LV-D6): the same tools, switches and access policy; a write is proposed through the Action Gateway and shown on the screen.
6. **Voice confirmation, Q-6 decided by the owner:** a `reversible` or `compensable` action may be approved by voice as the Leo architecture §8.4 says — the server reads back its preview, `noul` judges the person's next phrase an approval and the voice model calls `confirm(action_id)`; `approved_via = voice`. Irreversible actions, tainted runs (taint ≥ external), screen-only friction and secrets stay on the screen.
7. **Limits and money** (LV-D7): one voice session per person, at most 30 minutes, closed after 2 minutes without speech; the F6 meter reserves each minute; **voice minutes count against the plan's monthly minutes** (BL-D3), as in the draft.
8. **Audio in the browser** (LV-D8): capture and playback in AudioWorklets, with echo cancellation, noise suppression and gain control; Leo stops at once when Gemini reports an interruption.
9. **No browser fallback** (LV-D9): when Live is unavailable, voice mode says why and offers the text chat; the Web Speech path is removed.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Speech synthesis of text answers (Gemini TTS), recognition in the browser | Turn by turn, no interruption, a second speech model and price in F6; the owner chose the live session |
| Keep Web Speech until `capture` | The owner wants Charon now |
| The token in the URL or a subprotocol header | URLs reach logs; a subprotocol carries it in a header the edge may log as well; `hello` keeps it in the stream |
| A browser fallback to Web Speech when Live fails | Two voice paths to keep correct, with different voices and abilities |
| Screen-only approval of every write by voice | The owner accepted §8.4's rule for reversible and compensable actions |

## Consequences

- SLICE_MAP §2.4's voice row now points to this ADR; the agent plan §3.7 names the package.
- The WS gateway gets its foundation here (WebSockets on `ws`, the WS boundary, slots, `server.shutdown`), which `capture`'s live transcription reuses.
- `Channel` and `ApprovedVia` gain `voice` in both homes; billing's minutes meter takes voice minutes.
- The Leo architecture's §17 Q-6 is decided: accept for reversible and compensable actions, screen for the rest.
