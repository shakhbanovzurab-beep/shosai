import type {
  AiModel,
  AiModelPatch,
  AiModelsResponse,
  ConnectionCheckResponse,
  ProviderStatus,
} from "../domain/contract";
import { CATALOG, DEFAULT_MODEL_ID } from "./demo-catalog";
import { buildModelsAndSpend, type ModelFlags } from "./demo-spend";

/*
 * Admin › AI-модели in the development mocks: the curated catalogue with simulated spend. The provider key
 * never reaches the browser, so the provider shows as not configured and the catalogue as the demo one.
 * Enabled/default flags live in memory, shared through globalThis so every module sees the same store.
 */

const shared = globalThis as typeof globalThis & {
  adminAiModelFlags?: Map<string, ModelFlags>;
};
shared.adminAiModelFlags ??= new Map(
  CATALOG.map((model) => [model.id, { enabled: model.usage.requests > 0, is_default: model.id === DEFAULT_MODEL_ID }]),
);
const flags = shared.adminAiModelFlags;
const flagsFor = (id: string): ModelFlags => flags.get(id) ?? { enabled: false, is_default: false };

const PROVIDER: ProviderStatus = {
  provider: "openrouter",
  key_configured: false,
  key_hint: null,
  credits: null,
  source: "demo",
  sync_error: null,
};

/* ---------- Public API for the route handlers ---------- */

export function getAiModels(): Promise<AiModelsResponse> {
  return Promise.resolve({ provider: { ...PROVIDER }, ...buildModelsAndSpend(null, flagsFor, new Date()) });
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

export function checkConnection(): Promise<ConnectionCheckResponse> {
  const message = "Ключ OPENROUTER_API_KEY не задан на сервере.";
  return Promise.resolve({
    ok: false,
    latency_ms: null,
    message,
    checked_at: new Date().toISOString(),
    provider: { ...PROVIDER },
  });
}
