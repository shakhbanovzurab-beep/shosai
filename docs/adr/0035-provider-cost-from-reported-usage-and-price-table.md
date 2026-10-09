# ADR 0035 — Cost rows take the provider's reported cost, else units × a versioned platform price

- **Status:** accepted by the owner on 2026-10-08 (F6 planning, decision F6-D2).
- **Package:** F6 (`core/ai`); read by S03 (credit debits), S09 (model registry), F6's admin reports.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §6 (platform tables), §8.1 "Cost", inv-9, §14 rule 4; [ADR 0005](0005-data-without-owner-in-eu-home.md); [ADR 0026](0026-leo-decision-layer-on-jev.md); [DATA_MAPPING.md](../plan/DATA_MAPPING.md) `provider_costs`; [F6 plan](../plan/packages/F6-platform-services.md).

## Context

The draft computed every cost as units × a price looked up in a hard-coded table (`services/llm/catalog_prices.py`) overlaid by the model registry synced daily from OpenRouter (`services/llm/catalog.py:628-692`). Its lessons:

- A model with no known price was metered at $0 with a warning (`cost_tracker.py:164-177`); the default transcription model had no hard-coded price.
- Prompt-cache discounts were never applied on chat paths: the multipliers were keyed by vendor and every chat row said `openrouter` (`cost_tracker.py:95-102, 156`).
- OpenRouter's own `usage.cost` was ignored for chat; web-search fees were not counted (`catalog_prices.py:12-14`); one translation model was billed at another's price (`voice_metering.py:26, 161-163`).
- Units were mixed: seconds, pages and documents in `input_tokens` (`spend_guard.py:96-110`).

The registry belongs to S09, which comes after F6 and depends on it; prices cannot wait for it.

## Decision

1. **Reported cost first.** When the provider reports the call's cost — OpenRouter for chat, vision, embeddings, rerank, image generation and web search (`usage.cost`), and Jev through OpenRouter's Decisions API — the cost row stores that amount with `cost_source = reported`. It already includes cache discounts, search fees and the route OpenRouter actually took.
2. **Otherwise units × price.** For providers that report units only — OpenAI Realtime (seconds), Google Gemini Live (tokens per modality), Deepgram and pyannote (seconds), Mistral OCR (pages) — the row stores units × the price in force, with `cost_source = priced` and the price row's id.
3. **`provider_prices`**, a platform table in the EU home (data without an owner, ADR 0005): `(provider, model, unit, price_usd per unit, effective_from, source)`, append-only; a new price is a new row with a later `effective_from`, never an edit. Units are a closed set: input token, cached input token, output token, audio second, page, document, request, image.
4. **Seeds and sync.** A migration seeds the direct providers' prices from the draft's `catalog_prices.py`. A daily periodic job of F6 reads OpenRouter's model list and appends a row for each changed token price, so reservations of OpenRouter calls have an estimate. S09's registry references prices by `(provider, model)` and owns everything else about a model.
5. **No price, no call.** A call to a model without a price in force — needed for the reservation estimate of every call, and for the cost of a `priced` call — is refused before it is sent, with `model_unpriced`, counted and logged. It is never metered at $0. A reported cost that is missing from a provider answer falls back to units × price and is counted.
6. **Every row keeps its units** in typed columns (`input_tokens`, `cached_tokens`, `output_tokens`, `units` with `unit`), so a price change can be replayed and reconciled against provider invoices.

## Alternatives considered

| Option | Why not |
|---|---|
| Our own table for every provider (the draft) | loses cache discounts, search fees and OpenRouter's routing; the amount drifts from the provider's invoice |
| Prices from S09's registry | F6 could not finish before S09, which depends on F6 |
| Provider-reported cost only | the direct providers report units, not money; reservations need an estimate before the call |

## Consequences

- Cost rows of OpenRouter calls equal OpenRouter's invoice line by line; the monthly reconciliation compares sums, not formulas.
- An operator adds a price row before a new direct-provider model is used; until then the call is refused with a code the logs and metrics show.
- `provider_prices` is one more platform table in the EU home, cached in each process for 60 s; a price change applies within a minute.

## Revisit when

- A direct provider starts reporting cost in its answers → its rows switch to `reported`.
- OpenRouter stops reporting `usage.cost` for a call kind → that kind switches to `priced`.
