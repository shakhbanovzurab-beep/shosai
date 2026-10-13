# ADR 0043 — Speech providers by task: OpenRouter transcribes, pyannote diarizes, no Deepgram

- **Status:** accepted by the owner on 2026-10-13; amended the same day for live sessions (F6 step 3b).
- **Packages:** F6 (steps 3a and 3b), meetings.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.3, §18.2; [F6 plan](../plan/packages/F6-platform-services.md) §3.3 and step 3; [ADR 0034](0034-platform-services-in-core.md), [ADR 0035](0035-provider-cost-from-reported-usage-and-price-table.md).

## Context

- §18.2 and the F6 plan listed five speech providers: OpenRouter, OpenAI audio (file transcription straight to OpenAI), Deepgram, pyannote, OpenAI Realtime, and Gemini Live.
- The draft transcribed files through Deepgram and through OpenAI directly, with OpenRouter as a fallback, and laid pyannote's speaker turns over Deepgram's transcript. Each extra path is another key, client, price list and failure mode.
- OpenRouter now serves speech-to-text (`POST /audio/transcriptions`): one API for OpenAI's, Mistral's, NVIDIA's and others' models, with the cost of each call in `usage.cost` (read on 2026-10-13).

## Decision

1. **Transcription of recordings goes through OpenRouter**, with the model the caller chooses. The port's `transcribe` has one adapter: OpenRouter.
2. **pyannote only diarizes.** `diarize` returns speaker turns; it does not transcribe (no STT orchestration). Speakers are numbered by first appearance. A job pyannote charged for and that then failed is recorded with the outcome `failed`.
3. **OpenAI is reached directly only for its Realtime models** (streaming transcription of a live meeting, F6 step 3b).
4. **Google Gemini Live serves simultaneous translation** and the voice assistant (F6 step 3b).
5. **Deepgram is not used**, and neither is a direct OpenAI file transcription path.

## Amendment: live sessions (F6 step 3b)

6. **A live meeting is transcribed by the model chosen for it:** an OpenRouter transcription model, phrase by phrase through `transcribe`, or an OpenAI Realtime model (`gpt-live-transcribe`, `gpt-realtime-whisper`) as one stream.
7. **Simultaneous translation runs on Gemini Live** with `gemini-3.5-live-translate-preview`, which translates as the speaker talks, or `gemini-3.8-live` as an interpreter with a chosen voice, waiting for the speaker's pause. `gemini-3.8-live` replaces `gemini-3.1-flash-live-preview`, which Google marks legacy, at the same price. OpenAI's `gpt-realtime-translate` is not used.
8. **Sessions run from the server** through the WS gateway (§4.2), with the provider keys in the plane. The draft's direct client sessions on ephemeral tokens, with usage reported by the client, are not carried over: the server meters what it sends and receives.
9. **Gemini is reached through google-genai** (§18.2). Its 2.30.1 requires websockets below 17, so websockets is held at 16.1.1 for both providers.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep Deepgram for transcription with speakers | pyannote's turns are more accurate on four or more voices (draft lesson), and transcription is available through OpenRouter |
| Transcribe files straight at OpenAI, as the draft did | A second path to the same models; OpenRouter already reports the cost of each call |
| Raw WebSocket for Gemini Live, like OpenAI | The owner chose the official client (§18.2) |
| Client-direct Gemini sessions on ephemeral tokens, as in the draft | Usage would be reported by the client; the WS gateway already carries live audio |
| pyannote's STT orchestration (text and speakers in one job) | Ties the transcription model to pyannote's short list; meetings use the model chosen in OpenRouter |

## Consequences

- One key fewer (`DEEPGRAM_API_KEY` is not introduced); the OpenRouter, pyannote, OpenAI and Gemini keys are required by the production gate.
- File transcription depends on OpenRouter's balance. In the draft, a balance under $0.50 made every audio request answer 402, and transcription stopped silently. The balance must be alerted on (F5); the failure is not silent here: it leaves as `provider_error` and the call is counted.
- Long recordings are cut into parts by the caller: OpenRouter refuses requests over 25 MB, and its upstream providers time out after 60 s.
- A recording's copy stays in pyannote's storage up to 48 hours and cannot be deleted sooner.
- Recordings are numbered with speakers by laying pyannote's turns over the transcript's segments, in the meetings slice.

## Revisit when

- OpenRouter's speech-to-text fails meetings' quality or latency targets, or its balance dependence causes an outage.
- A provider offers transcription with speakers as accurate as pyannote's at a lower total price.
