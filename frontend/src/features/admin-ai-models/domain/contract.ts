/**
 * Admin › AI-модели API contract, shared by the slice's UI and its route handlers in
 * `src/features/admin-ai-models/server` (served at `/api/admin/ai-models*`). They proxy to
 * `${BACKEND_API_URL}/v1/admin/ai-models*` when it is set. Without a backend they answer from
 * `src/features/admin-ai-models/server/ai-models.ts`: live OpenRouter catalogue and credits when
 * `OPENROUTER_API_KEY` is set, demo data otherwise; spend is always demo there. snake_case to match
 * Pydantic; errors are FastAPI's `{ "detail": string }`. Money is in USD. The OpenRouter key itself
 * never leaves the server: only whether it is set and its last characters.
 */

import { z } from "zod";

/* ---------- Provider: part of GET /admin/ai-models ---------- */

/** Where the numbers come from: the backend, the live OpenRouter API (spend still demo), or demo data. */
export type AiDataSource = "backend" | "openrouter" | "demo";

export type OpenRouterCredits = {
  /** Credits ever bought, USD. */
  total: number;
  /** Credits spent, USD. */
  used: number;
  /** total − used, USD. */
  remaining: number;
};

export type ProviderStatus = {
  provider: "openrouter";
  /** Whether `OPENROUTER_API_KEY` is set on the server. */
  key_configured: boolean;
  /** The key's last characters, e.g. "…9f2c"; null when it is not set. */
  key_hint: string | null;
  /** null when unknown: no key, or OpenRouter did not answer. */
  credits: OpenRouterCredits | null;
  source: AiDataSource;
  /** Why live data could not be loaded, shown next to the status; null when all went well. */
  sync_error: string | null;
};

/* ---------- Spend: part of GET /admin/ai-models ---------- */

export type DailySpend = {
  /** ISO date, YYYY-MM-DD. */
  date: string;
  /** USD. */
  cost: number;
};

export type SpendSummary = {
  /** USD, since midnight UTC. */
  today: number;
  /** USD, since the 1st of the month (UTC). */
  month: number;
  /** USD, this month's spend extrapolated to the end of the month at the current daily rate. */
  forecast_month: number;
  tokens_in_month: number;
  tokens_out_month: number;
  /** The last 30 days, oldest first, today last. */
  daily: DailySpend[];
};

/* ---------- Models: part of GET /admin/ai-models, PATCH /admin/ai-models/{id} ---------- */

export type AiModel = {
  /** URL-safe key used in PATCH paths, e.g. "claude-sonnet-4-5". */
  id: string;
  /** OpenRouter's model id, e.g. "anthropic/claude-sonnet-4.5". */
  openrouter_id: string;
  name: string;
  /** Who makes the model, e.g. "Anthropic". */
  provider: string;
  /** Tokens. */
  context_length: number;
  /** USD per 1M input (prompt) tokens. */
  price_input_per_m: number;
  /** USD per 1M output (completion) tokens. */
  price_output_per_m: number;
  /** USD spent on this model this month. */
  month_spend: number;
  month_requests: number;
  /** Whether users may pick the model. */
  enabled: boolean;
  /** The model Leo uses when the user has not picked one. Exactly one model is the default, and it is enabled. */
  is_default: boolean;
};

export type AiModelsResponse = {
  provider: ProviderStatus;
  spend: SpendSummary;
  models: AiModel[];
};

/**
 * One change at a time. Disabling the default model is refused (422), as is making a disabled
 * model the default. Answers with the updated model; making one the default unsets the previous one.
 */
export type AiModelPatch = { enabled: boolean } | { is_default: true };

/** What PATCH accepts: exactly one of the two changes. */
export const aiModelPatchSchema = z.union([
  z.strictObject({ enabled: z.boolean() }),
  z.strictObject({ is_default: z.literal(true) }),
]);

/* ---------- Connection check: POST /admin/ai-models/check ---------- */

export type ConnectionCheckResponse = {
  ok: boolean;
  /** Round trip to OpenRouter in milliseconds; null when no request was made. */
  latency_ms: number | null;
  /** A human-readable result in Russian, shown in the toast. */
  message: string;
  /** ISO timestamp. */
  checked_at: string;
  /** The provider status as of the check, credits included. */
  provider: ProviderStatus;
};
