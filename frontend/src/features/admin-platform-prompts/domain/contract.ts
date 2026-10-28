import type { components } from "@/lib/api/generated/schema";

/**
 * Контракт экрана «Промты платформы» — сгенерированные типы `/v1/admin/platform-prompts*` (studio, шаг 6, ST-D1):
 * системный промт, правила и запрещённые темы, дополнения двух функций; черновик, версии и откат. Ошибки — коды
 * конверта ADR 0008, их слова — в `problems.ts`. Лимиты повторяют домен studio (`platform_layer.py`).
 */
type Schemas = components["schemas"];

export type PlatformConfig = Schemas["AdminPlatformConfig"];
export type DraftPatch = Schemas["AdminPlatformDraftPatch"];
export type PlatformDraft = Schemas["AdminPlatformDraft"];
export type PlatformVersion = Schemas["AdminPlatformVersion"];
export type VersionSummary = Schemas["AdminPlatformVersionSummary"];
export type VersionsPage = Schemas["Page_AdminPlatformVersionSummary_"];
export type PlatformPromptsState = Schemas["AdminPlatformPrompts"];
export type SafetyRules = Schemas["AdminSafety"];
export type GuardrailRule = Schemas["AdminSafetyRule"];
export type FeaturePrompt = Schemas["AdminFeaturePrompt"];
export type FeatureId = keyof Schemas["AdminFeatures"];

export const SYSTEM_PROMPT_MAX = 20_000;
export const FEATURE_PROMPT_MAX = 8_000;
export const RULE_MAX = 500;
export const RULE_ID_MAX = 64;
export const RULES_LIMIT = 50;
export const TOPIC_MAX = 80;
export const TOPICS_LIMIT = 100;
export const COMMENT_MAX = 280;
/** Бюджет слоя платформы: системный промт, включённые правила и темы вместе. */
export const LAYER_TOKENS = 1_000;
/** Бюджет дополнения одной функции. */
export const FEATURE_TOKENS = 500;

/** Функции со своим вызовом модели, которые берут дополнение оператора. */
export const FEATURES = [
  {
    id: "meeting_summary",
    label: "Саммари встречи",
    description: "Добавляется к промту итогов записи в заметках. Слой платформы в этот вызов не попадает.",
  },
  {
    id: "voice_mode",
    label: "Голосовой режим",
    description: "Добавляется к слою платформы, пока Leo разговаривает голосом.",
  },
] as const satisfies readonly { id: FeatureId; label: string; description: string }[];
