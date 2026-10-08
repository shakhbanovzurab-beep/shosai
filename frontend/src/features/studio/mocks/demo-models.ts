import {
  MIN_MAX_TOKENS,
  type ModelInfo,
  type ModelsResponse,
  type RoleModelSettings,
  type StudioRole,
  type UpdateRoleModelRequest,
} from "../domain/contract";
import { ROLES, roleById } from "../domain/roles";
import type { Problem } from "./problems";

/** Stand-in for the models on the user's subscription. The real list comes from the backend. */
const MODELS: ModelInfo[] = [
  {
    id: "minimax-m3",
    provider: "MiniMax",
    name: "MiniMax M3",
    tier: "standard",
    capabilities: ["text"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 32768,
  },
  {
    id: "mistral-small-4",
    provider: "Mistral",
    name: "Mistral Small 4",
    tier: "standard",
    capabilities: ["text", "vision"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 32768,
  },
  {
    id: "deepseek-v4-pro-0423",
    provider: "DeepSeek",
    name: "DeepSeek V4 Pro 0423",
    tier: "standard",
    capabilities: ["text"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 65536,
  },
  {
    id: "deepseek-v4-flash-0423",
    provider: "DeepSeek",
    name: "DeepSeek V4 Flash 0423",
    tier: "standard",
    capabilities: ["text"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 65536,
  },
  {
    id: "muse-voice-transcribe-1.0",
    provider: "Meta",
    name: "Muse Voice Transcribe 1.0",
    tier: "standard",
    capabilities: ["speech_to_text"],
    supports_temperature: false,
    supports_reasoning: false,
    max_output_tokens: 8192,
  },
  {
    id: "claude-opus-5-5",
    provider: "Anthropic",
    name: "Claude Opus 5.5",
    tier: "frontier",
    capabilities: ["text", "vision"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 64000,
  },
  {
    id: "claude-fable-5-1",
    provider: "Anthropic",
    name: "Claude Fable 5.1",
    tier: "frontier",
    capabilities: ["text", "vision"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 64000,
  },
  {
    id: "gpt-astra",
    provider: "OpenAI",
    name: "GPT Astra",
    tier: "frontier",
    capabilities: ["text", "vision"],
    supports_temperature: true,
    supports_reasoning: true,
    max_output_tokens: 64000,
  },
];

const DEFAULTS: Record<StudioRole, Pick<RoleModelSettings, "model_id" | "max_tokens">> = {
  live_answers: { model_id: "minimax-m3", max_tokens: 4096 },
  screenshots: { model_id: "mistral-small-4", max_tokens: 4096 },
  code: { model_id: "deepseek-v4-pro-0423", max_tokens: 4096 },
  system_design: { model_id: null, max_tokens: 4096 },
  notes: { model_id: "deepseek-v4-flash-0423", max_tokens: 8192 },
  transcript: { model_id: "muse-voice-transcribe-1.0", max_tokens: 4096 },
};

// In-memory stand-in used when BACKEND_API_URL is unset; on globalThis so every route bundle shares it.
const shared = globalThis as typeof globalThis & { studioDemoRoles?: RoleModelSettings[] };
shared.studioDemoRoles ??= ROLES.map((role) => ({
  role: role.id,
  ...DEFAULTS[role.id],
  temperature: 0.7,
  reasoning: false,
}));
const roles = shared.studioDemoRoles;

export const listModels = (): ModelsResponse => ({ models: MODELS, roles });

/** Whether the demo catalogue has a text model with this id (Settings › Leo model accepts those, or "auto"). */
export const isSubscriptionTextModel = (id: string) =>
  MODELS.some((m) => m.id === id && m.capabilities.includes("text"));

/** Validates and saves one role's settings. Returns the saved settings, or why they were refused. */
export function updateRole(role: StudioRole, body: UpdateRoleModelRequest): RoleModelSettings | Problem {
  const definition = roleById(role);
  const model = body.model_id === null ? null : MODELS.find((m) => m.id === body.model_id);
  if (!definition) return { code: "unknownRole" };
  if (model === undefined) return { code: "modelNotOnPlan" };
  if (model && !model.capabilities.includes(definition.requires)) {
    return { code: "modelCantDoRole", model: model.name, role };
  }
  const limit = model?.max_output_tokens ?? 65536;
  if (body.max_tokens < MIN_MAX_TOKENS || body.max_tokens > limit) {
    return { code: "maxTokensRange", min: MIN_MAX_TOKENS, max: limit };
  }
  const saved: RoleModelSettings = {
    role,
    model_id: body.model_id,
    temperature: Math.min(2, Math.max(0, body.temperature)),
    max_tokens: Math.round(body.max_tokens),
    reasoning: Boolean(model?.supports_reasoning && body.reasoning),
  };
  const index = roles.findIndex((r) => r.role === role);
  roles[index] = saved;
  return saved;
}
