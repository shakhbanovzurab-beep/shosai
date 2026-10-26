import type { components } from "@/lib/api/generated/schema";

/**
 * Studio API contract, shared by the UI and the route handlers in `server/` (mounted under
 * `src/app/api/studio`). The handlers proxy to the FastAPI backend at `BACKEND_API_URL` (paths
 * below, under `/v1/studio`) and fall back to an in-memory demo when it is unset. snake_case to
 * match Pydantic; errors are FastAPI's `{ "detail": string }`, worded in the request's interface language
 * (the `ui_language` cookie). See docs/studio-api.md.
 */

/** The jobs the assistant does; each has its own model and prompt. */
export const STUDIO_ROLES = ["live_answers", "screenshots", "code", "system_design", "notes", "transcript"] as const;
export type StudioRole = (typeof STUDIO_ROLES)[number];

/* ---------- Context: GET /context, PUT /context ---------- */

/** Inserted as the first system message of every model request. */
export type StudioContext = { content: string; updated_at: string | null };
export const CONTEXT_MAX_CHARS = 4000;

/* ---------- Prompts: GET|POST /prompts, PATCH|DELETE /prompts/{id}, PUT /prompts/active ---------- */

/** The user's instructions for one role, optionally extended with installed skills. */
export type Prompt = {
  id: string;
  name: string;
  role: StudioRole;
  content: string;
  /** Installed skills (see /skills) appended to the instructions, in this order. */
  skill_ids: string[];
  updated_at: string;
};

export type PromptsResponse = {
  prompts: Prompt[];
  /** The prompt each role plays by; null falls back to the built-in default. */
  active: Record<StudioRole, string | null>;
};

export type PromptDraft = Pick<Prompt, "name" | "role" | "content" | "skill_ids">;
export type SetActivePromptRequest = { role: StudioRole; prompt_id: string | null };

export const PROMPT_NAME_MAX = 80;
export const PROMPT_CONTENT_MAX = 20000;
/** The most installed skills one prompt can use. */
export const PROMPT_SKILLS_MAX = 20;

/*
 * ---------- Skills ----------
 * Leo's skills store, on the API since agent step 15: `/v1/agent/skills*` (see `api/skills-api.ts`).
 */

/** A SKILL.md-based instruction installed from GitHub, pinned to the commit it was read at. */
export type Skill = components["schemas"]["SkillOut"];
export type SkillsResponse = components["schemas"]["SkillsOut"];
/** A skill found in the skills.sh directory or in a repository, not yet installed. */
export type SkillCandidate = components["schemas"]["SkillCandidateOut"];
export type SkillSearchResponse = components["schemas"]["SkillSearchOut"];

/* ---------- Models: GET /models, PUT /models/roles/{role} ---------- */

export type ModelCapability = "text" | "vision" | "speech_to_text";

/** A model on the user's subscription; the list only contains what they can use. */
export type ModelInfo = {
  id: string;
  provider: string;
  name: string;
  /** Frontier models are the expensive ones; they draw on the weekly frontier allowance (Settings › Usage). */
  tier: "standard" | "frontier";
  capabilities: ModelCapability[];
  supports_temperature: boolean;
  supports_reasoning: boolean;
  max_output_tokens: number;
};

export type RoleModelSettings = {
  role: StudioRole;
  model_id: string | null;
  /** 0–2; ignored when the model doesn't support it. */
  temperature: number;
  max_tokens: number;
  /** Ignored when the model doesn't support it. */
  reasoning: boolean;
};

export type ModelsResponse = { models: ModelInfo[]; roles: RoleModelSettings[] };
export type UpdateRoleModelRequest = Omit<RoleModelSettings, "role">;

export const MIN_MAX_TOKENS = 256;
