import type {
  AiModel,
  AiModelPatch,
  AiModelsResponse,
  ConnectionCheckResponse,
  OpenRouterCredits,
  ProviderStatus,
} from "../domain/contract";
import { CATALOG, DEFAULT_MODEL_ID } from "./demo-catalog";
import { buildModelsAndSpend, type LiveModel, type ModelFlags } from "./demo-spend";

/*
 * Admin › AI-модели without a backend. When `OPENROUTER_API_KEY` is set, the curated catalogue's
 * names, context lengths and prices come from OpenRouter's /models and the balance from /credits.
 * Spend is always simulated, since OpenRouter does not report per-model usage for a key.
 * Enabled/default flags live in memory, shared through globalThis so every route module sees the
 * same store. The key is only ever read here and never leaves the server.
 */

const OPENROUTER_API = "https://openrouter.ai/api/v1";
const CATALOG_TTL_MS = 10 * 60 * 1000;
const TIMEOUT_MS = 8000;

const shared = globalThis as typeof globalThis & {
  adminAiModelFlags?: Map<string, ModelFlags>;
  adminAiModelCatalog?: { at: number; models: Map<string, LiveModel> };
};
shared.adminAiModelFlags ??= new Map(
  CATALOG.map((model) => [model.id, { enabled: model.usage.requests > 0, is_default: model.id === DEFAULT_MODEL_ID }]),
);
const flags = shared.adminAiModelFlags;
const flagsFor = (id: string): ModelFlags => flags.get(id) ?? { enabled: false, is_default: false };

/* ---------- OpenRouter ---------- */

const apiKey = () => process.env.OPENROUTER_API_KEY?.trim() || null;

/** Last four characters only, and only when the key is long enough that they give nothing away. */
function keyHint(key: string | null) {
  if (!key) return null;
  return key.length >= 16 ? `…${key.slice(-4)}` : "…";
}

const providerStatus = (key: string | null): ProviderStatus => ({
  provider: "openrouter",
  key_configured: key !== null,
  key_hint: keyHint(key),
  credits: null,
  source: "demo",
  sync_error: null,
});

class OpenRouterError extends Error {}

async function openRouter<T>(path: string, key: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${OPENROUTER_API}${path}`, {
      headers: { authorization: `Bearer ${key}` },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    throw new OpenRouterError("OpenRouter не отвечает.");
  }
  if (res.status === 401 || res.status === 403) throw new OpenRouterError(`OpenRouter отклонил ключ (${res.status}).`);
  if (!res.ok) throw new OpenRouterError(`OpenRouter ответил ошибкой ${res.status}.`);
  return (await res.json()) as T;
}

type OpenRouterModel = {
  id: string;
  name?: string;
  context_length?: number;
  pricing?: { prompt?: string; completion?: string };
};

/** Price per token as OpenRouter's decimal string → USD per 1M tokens. */
const perMillion = (value: string | undefined, fallback: number) => {
  const price = Number(value);
  return Number.isFinite(price) && price >= 0 ? Math.round(price * 1e6 * 1e4) / 1e4 : fallback;
};

async function liveCatalog(key: string): Promise<Map<string, LiveModel>> {
  const cached = shared.adminAiModelCatalog;
  if (cached && Date.now() - cached.at < CATALOG_TTL_MS) return cached.models;
  const { data } = await openRouter<{ data?: OpenRouterModel[] }>("/models", key);
  const wanted = new Map(CATALOG.map((entry) => [entry.openrouter_id, entry]));
  const models = new Map<string, LiveModel>();
  for (const model of data ?? []) {
    const entry = wanted.get(model.id);
    if (!entry) continue;
    models.set(model.id, {
      // OpenRouter prefixes names with the maker, e.g. "Anthropic: Claude Sonnet 4.5".
      name: model.name?.replace(/^[^:]+:\s*/, "") || entry.name,
      context_length: model.context_length ?? entry.context_length,
      price_input_per_m: perMillion(model.pricing?.prompt, entry.price_input_per_m),
      price_output_per_m: perMillion(model.pricing?.completion, entry.price_output_per_m),
    });
  }
  shared.adminAiModelCatalog = { at: Date.now(), models };
  return models;
}

async function liveCredits(key: string): Promise<OpenRouterCredits> {
  const { data } = await openRouter<{ data?: { total_credits?: number; total_usage?: number } }>("/credits", key);
  const total = data?.total_credits ?? 0;
  const used = data?.total_usage ?? 0;
  return { total, used, remaining: Math.max(0, total - used) };
}

const errorText = (reason: unknown) =>
  reason instanceof OpenRouterError ? reason.message : "Не удалось получить данные OpenRouter.";

/* ---------- Public API for the route handlers ---------- */

export async function getAiModels(): Promise<AiModelsResponse> {
  const key = apiKey();
  const provider = providerStatus(key);
  let live: Map<string, LiveModel> | null = null;
  if (key) {
    const [catalog, credits] = await Promise.allSettled([liveCatalog(key), liveCredits(key)]);
    if (catalog.status === "fulfilled") live = catalog.value;
    if (credits.status === "fulfilled") provider.credits = credits.value;
    const failure = [catalog, credits].find((result) => result.status === "rejected");
    provider.source = live ? "openrouter" : "demo";
    provider.sync_error = failure ? errorText(failure.reason) : null;
  }
  return { provider, ...buildModelsAndSpend(live, flagsFor, new Date()) };
}

export type PatchResult = { model: AiModel } | { error: string; status: number };

export async function patchAiModel(id: string, change: AiModelPatch): Promise<PatchResult> {
  const current = flags.get(id);
  if (!current) return { error: "Модель не найдена.", status: 404 };
  if ("enabled" in change) {
    if (!change.enabled && current.is_default)
      return { error: "Сначала выберите другую модель по умолчанию.", status: 422 };
    flags.set(id, { ...current, enabled: change.enabled });
  } else {
    if (!current.enabled) return { error: "Включите модель, прежде чем делать её моделью по умолчанию.", status: 422 };
    for (const [otherId, other] of flags) flags.set(otherId, { ...other, is_default: otherId === id });
  }
  const { models } = await getAiModels();
  const model = models.find((item) => item.id === id);
  return model ? { model } : { error: "Модель не найдена.", status: 404 };
}

export async function checkConnection(): Promise<ConnectionCheckResponse> {
  const key = apiKey();
  const checkedAt = () => new Date().toISOString();
  const provider = providerStatus(key);
  if (!key) {
    const message = "Ключ OPENROUTER_API_KEY не задан на сервере.";
    return { ok: false, latency_ms: null, message, checked_at: checkedAt(), provider };
  }
  const started = performance.now();
  try {
    provider.credits = await liveCredits(key);
    provider.source = "openrouter";
    const latency = Math.round(performance.now() - started);
    return {
      ok: true,
      latency_ms: latency,
      message: `Подключение работает, ответ за ${latency} мс.`,
      checked_at: checkedAt(),
      provider,
    };
  } catch (reason) {
    provider.sync_error = errorText(reason);
    return {
      ok: false,
      latency_ms: Math.round(performance.now() - started),
      message: provider.sync_error,
      checked_at: checkedAt(),
      provider,
    };
  }
}
