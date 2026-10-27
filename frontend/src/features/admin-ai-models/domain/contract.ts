import type { components } from "@/lib/api/generated/schema";

/**
 * Контракт экрана AI-моделей — сгенерированные типы `/v1/admin/ai-models*` (studio, шаг 4). Деньги — в
 * долларах числами, даты — деловые (ADR 0058); ошибки — коды конверта ADR 0008, их слова — в `problems.ts`.
 */
type Schemas = components["schemas"];

export type AiModel = Schemas["AdminAiModel"];
export type AiModelsResponse = Schemas["AdminAiModels"];
export type ProviderStatus = Schemas["AdminProviderStatus"];
export type OpenRouterCredits = Schemas["AdminCredits"];
export type SpendSummary = Schemas["AdminSpendSummary"];
export type DailySpend = Schemas["AdminDailySpend"];
export type RoleDefault = Schemas["AdminRoleDefault"];
export type ConnectionCheckResponse = Schemas["AdminConnectionCheck"];
export type ModelRole = Schemas["ModelRole"];
export type Tier = Schemas["Tier"];
export type TierDecision = Schemas["AdminTierDecision"]["decision"];
