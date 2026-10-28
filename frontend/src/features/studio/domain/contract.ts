import type { components } from "@/lib/api/generated/schema";

/**
 * Контракт Studio — сгенерированные типы `/v1/studio/*` (studio, шаг 8) и навыков Leo `/v1/agent/skills*`
 * (agent, шаг 15). Ошибки — коды конверта ADR 0008, их слова — в каталоге `studioApi` (`studio-problems.ts`).
 * Лимиты повторяют домен studio (`prompts.py`, `roles.py`). См. docs/studio-api.md.
 */
type Schemas = components["schemas"];

/** Роли, в которых человек выбирает свою модель и свой промт; у каждой своя модель и свой промт. */
export const STUDIO_ROLES = ["live_answers", "screenshots", "code", "system_design", "notes"] as const;
export type StudioRole = Schemas["PromptRole"];

/** Слова человека о себе; учитываются в каждом ответе ему, кроме записей встреч. */
export type StudioContext = Schemas["StudioContext"];
export const CONTEXT_MAX_CHARS = 4000;

/** Указания человека для одной роли, с установленными навыками по порядку. */
export type Prompt = Schemas["StudioPrompt"];
/** Промты человека и промт, по которому играет каждая роль; null — встроенный. */
export type PromptsResponse = Schemas["StudioPrompts"];
export type PromptDraft = Pick<Prompt, "name" | "role" | "content" | "skill_ids">;

export const PROMPT_NAME_MAX = 80;
export const PROMPT_CONTENT_MAX = 20000;
/** Сколько установленных навыков может взять один промт. */
export const PROMPT_SKILLS_MAX = 20;

/** Навык из SKILL.md, установленный с GitHub и закреплённый на коммите, с которого прочитан. */
export type Skill = Schemas["SkillOut"];
export type SkillsResponse = Schemas["SkillsOut"];
/** Навык из каталога skills.sh или репозитория, ещё не установленный. */
export type SkillCandidate = Schemas["SkillCandidateOut"];
export type SkillSearchResponse = Schemas["SkillSearchOut"];

export type ModelCapability = Schemas["ModelCapability"];
/** Модель, которую предлагает тариф человека; frontier — только на тарифе с frontier-моделями. */
export type ModelInfo = Schemas["StudioModel"];
/** Модель роли и как её вызывают; модели нет — модель роли по умолчанию. */
export type RoleModelSettings = Schemas["StudioRoleModel"];
export type ModelsResponse = Schemas["StudioModels"];
export type UpdateRoleModelRequest = Schemas["StudioRoleModelUpdate"];

export const MIN_MAX_TOKENS = 256;
/** Потолок ответа для любой модели; у модели свой предел может быть ниже. */
export const MAX_MAX_TOKENS = 32768;
