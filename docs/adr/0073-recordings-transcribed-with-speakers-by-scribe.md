# ADR 0073 — Recordings are transcribed with speakers by Scribe; pyannote is removed

- **Status:** accepted by the owner on 2026-10-27, after the pilot of the same day (notes plan MT-D14). The owner decided points 1 and 2; points 3–8 are *agent-derived* detailing from the pilot's measurements, stated so the owner can correct them.
- **Packages:** notes (step 29), F6 (the speech port).
- **Context documents:** [ADR 0043](0043-speech-providers-by-task.md) (point 2 and its consequences are superseded here), [ADR 0035](0035-provider-cost-from-reported-usage-and-price-table.md), [notes plan](../plan/slices/notes.md) MT-D3, MT-D14 and step 29; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.3, §10, §18.2.

## Context

Uploaded and desktop recordings were transcribed by `openai/whisper-large-v3` through OpenRouter, in parts of 5 minutes. pyannote then found the speakers over the whole file, and the align stage laid its turns over the transcript. On staging, pyannote's key has answered 402 since 2026-10-21, so recordings have had no speakers.

The pilot of 2026-10-27 compared the two paths on FLEURS. It used 16 languages of about 3 minutes each, a Russian recording of 99.4 minutes and a seam test. It spent $0.87 of a $1 budget:

- **Text.** `elevenlabs/scribe-v2` makes fewer errors than whisper in all 16 languages: 5.6 % on average against 13.8 %.
- **Speakers.** In one request, Scribe kept every turn to one voice and caught all 641 changes between a male and a female voice. It recognised the same voice later in the recording in 17 cases of 24.
- **Long recordings.**
  - The 99.4-minute recording went in one request and was answered in 80 s.
  - The 25 MB limit applies to the file, not to its base64: a body of 31.7 MB carrying 22.7 MB of audio was accepted.
  - At 16 and 12 kbps, text and speakers stayed as good as at 32 kbps.
- **Separate requests.** A stretch cut into two requests lost its voices at the cut: 0 of 6 were recognised across it, against 4 of 6 in one request.
- **Price.** Scribe costs $0.22 an hour. Whisper costs $0.027–0.111 an hour; pyannote adds €19 a month, which includes about 170 hours, and €0.112 for each hour beyond. Scribe is cheaper up to about 110–125 hours a month and 21–39 % dearer above that.

## Decision

1. **Recordings are transcribed with speakers in one call** by `elevenlabs/scribe-v2` through OpenRouter. The call passes ElevenLabs' `diarize` in `provider.options` and asks for word timestamps. Each word comes back with its speaker. This covers imports from the cabinet and the native clients, and desktop recordings. *(owner)*
2. **pyannote is removed entirely** — its adapter, the port's `diarize`, `PYANNOTE_API_KEY` and its settings, its prices, its dashboard rows, the diarize stage and `NOTES_DIARIZE_MODEL`. *(owner)*
3. **The port's `transcribe` takes `speakers`.**
   - When it is set, the OpenRouter adapter asks for `verbose_json` with word granularity and passes the speaker options of the providers that diarize (today ElevenLabs).
   - OpenRouter forwards only the options of the provider that serves the request, so another model ignores them.
   - Words that carry speakers become segments: one per run of a voice, broken at a pause over 800 ms. The text is cut from the answer's own text, so scripts written without spaces keep their spacing.
4. **A recording's run is intake → transcribe → align → findings → write-up.** Every stage is critical: speakers arrive with the text, so no non-critical stage is left.
5. **Parts of at most 90 minutes.** A recording of up to 90 minutes goes whole. A longer one is cut into parts of at most 90 minutes at a pause, at 24 kbps as before.
   - 90 minutes is below what the pilot measured in one request (99.4 minutes answered in 80 s). A transcription waits up to 300 s for its answer and 120 s to send its body, longer than other OpenRouter calls (120 s and 30 s), and the stage gives each part 5 minutes.
   - How OpenRouter answers longer requests was not measured.
6. **Voices are carried across a cut.**
   - Each part is heard a minute past each of its cuts, so two neighbouring parts both hear the same two minutes around their cut. That audio is used only to match voices: each part keeps the segments whose middle lies in its own span, so the two minutes are written once.
   - A voice of the later part takes the number of the earlier part's voice it speaks with at the same time, when at least two thirds of its shared speech and at least 3 seconds agree; pairs are taken from the largest agreement down, one to one.
   - In a desktop recording, the voice most over the live "me" lines in each part is the owner in every part.
   - A voice found nowhere earlier gets a new number. A wrong merge would attribute one person's words to another, so an unmatched voice stays apart.
7. **A fallback that does not mark speakers** (`NOTES_TRANSCRIBE_FALLBACK_MODEL`, for example whisper) still gives the transcript and the notes. Its lines carry no speaker, and the stage logs the recording as heard without speakers.
8. **Price.** OpenRouter reports the cost of each call (ADR 0035). A seed price of $0.0000611111 per second of audio, from OpenRouter's endpoint list, admits the model and prices an answer that lost its cost. The two minutes heard by both parts at each cut are paid twice. The pyannote seed prices are deleted with the provider.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep whisper + pyannote | Two providers and two failure modes; pyannote has been out of credit since 2026-10-21; whisper's text is worse in every platform language. It is cheaper only above about 110–125 hours a month. |
| Short parts, each heard alone, as whisper had | Voices are numbered anew in every part: 0 of 6 were recognised across a cut in the pilot. |
| One request for every recording, at 12 kbps | Text and speakers hold at 12 kbps, and 4.4 hours fit in 23 MiB. But no request longer than 99 minutes was measured, and a long wait risks the client's and OpenRouter's timeouts. Revisit with a measurement. |
| ElevenLabs' own API (files up to 10 hours, asynchronous with a webhook) | One request for every recording, voices consistent throughout. But it needs a second provider key and path, and a public webhook. For the owner to decide if cuts prove to hurt. |
| Overlap stitching that merges every voice it can | A wrong merge gives one person's words to another; an honest new number is the lesser error. |

## Consequences

- One key fewer: the production gate no longer requires `PYANNOTE_API_KEY`, and no recording copy sits in pyannote's storage for 48 hours. The audio goes to ElevenLabs through OpenRouter, under the same cross-border consent rule.
- Revision `c4d1f7a9e2b6` drops `meeting_processing_runs.turns_key` and takes `diarize` out of every run's stage state.
  - A run that was at that stage goes on to align, with its transcript from the parts already heard.
  - The downgrade brings the column back but not the removed stage records.
  - The same revision deletes the pyannote price rows and seeds Scribe's price.
- Transcription costs about eight times whisper's price per hour. Below about 110–125 hours a month that is cheaper than whisper + pyannote, above it 21–39 % dearer. Desktop recordings use the same path, so their volume decides it.
- In a recording over 90 minutes, a voice silent in the two minutes around a cut may get a second number after it. The owner of a desktop recording is kept by the "me" lines.
- Live meetings (OpenAI Realtime or phrase by phrase through OpenRouter) and Shosai's video calls (one participant per track, ADR 0072) do not diarize and are unchanged.

## Revisit when

- Cuts in recordings over 90 minutes visibly split people, or recordings over 90 minutes become common: measure one request of 3–4 hours at 12–16 kbps through OpenRouter, or weigh ElevenLabs' own API.
- The volume of recordings stays above about 125 hours a month and the price difference matters more than one provider and better text.
- OpenRouter's speech-to-text or ElevenLabs fails the quality or latency targets.
