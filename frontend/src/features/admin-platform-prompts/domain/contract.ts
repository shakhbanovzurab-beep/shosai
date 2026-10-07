/**
 * Platform prompts API contract: the global Leo configuration that sits above every user's Studio.
 * Shared by the admin screen (`/admin/platform-prompts`) and the route handlers in
 * `server/platform-prompts-route.ts` (mounted under `src/app/api/admin/platform-prompts`). They proxy
 * to `${BACKEND_API_URL}/v1/admin/platform-prompts/*` when it is set and fall back to an in-memory demo
 * otherwise. snake_case to match Pydantic; errors are FastAPI's `{ "detail": string }`.
 *
 * Endpoints:
 * - GET    /platform-prompts                        → PlatformPromptsState
 * - PATCH  /platform-prompts/draft                  ← PlatformPromptConfigPatch → PlatformPromptDraft
 * - POST   /platform-prompts/publish                ← PublishRequest → PlatformPromptsState
 * - POST   /platform-prompts/versions/{id}/restore  ← RestoreRequest (optional) → PlatformPromptsState
 *
 * Request assembly order for every chat turn: platform system prompt (+ the active feature prompt and
 * enabled guardrail rules) → the user's Studio context and role prompt → the user's message.
 */

/* ---------- Behaviour defaults ---------- */

export const TONES = [
  { id: "concise", label: "Кратко" },
  { id: "balanced", label: "Сбалансированно" },
  { id: "detailed", label: "Подробно" },
] as const;
export type Tone = (typeof TONES)[number]["id"];

/** "user" answers in the language of the question; "fixed" always answers in `fixed_language`. */
export type LanguagePolicy = "user" | "fixed";

/** Settings a user may change for themselves in Studio / Settings › Leo. Anything not listed is locked. */
export const OVERRIDABLE_SETTINGS = [
  { id: "tone", label: "Стиль ответов", description: "Кратко, сбалансированно или подробно" },
  { id: "language", label: "Язык ответов", description: "Свой язык вместо политики платформы" },
  { id: "model", label: "Модель", description: "Выбор модели из своей подписки" },
  { id: "temperature", label: "Температура", description: "Креативность ответов" },
  { id: "max_output_tokens", label: "Длина ответа", description: "Лимит токенов в ответе" },
  { id: "web_search", label: "Веб-поиск", description: "Отключить поиск для себя" },
  { id: "system_context", label: "Личный контекст", description: "Свой контекст и промты ролей в Studio" },
] as const;
export type OverridableSetting = (typeof OVERRIDABLE_SETTINGS)[number]["id"];

export type BehaviorDefaults = {
  tone: Tone;
  language_policy: LanguagePolicy;
  /** A language code from src/lib/language.ts; used only when `language_policy` is "fixed". */
  fixed_language: string;
  /** A model id; users without access to it fall back to their subscription's default. */
  default_model: string;
  /** 0–2. */
  temperature: number;
  max_output_tokens: number;
  web_search: boolean;
  user_overrides: OverridableSetting[];
};

export const TEMPERATURE_MIN = 0;
export const TEMPERATURE_MAX = 2;
export const OUTPUT_TOKENS_MIN = 256;
export const OUTPUT_TOKENS_MAX = 32_000;

/* ---------- Safety ---------- */

export type GuardrailRule = { id: string; text: string; enabled: boolean };

/** Agent actions Leo may never run without the user confirming them in the chat first. */
export const CONFIRM_ACTIONS = [
  { id: "send_email", label: "Отправка писем" },
  { id: "delete_files", label: "Удаление файлов и заметок" },
  { id: "payments", label: "Платежи и покупки" },
  { id: "calendar_invites", label: "Приглашения в календарь" },
  { id: "share_externally", label: "Доступ к файлам для внешних людей" },
  { id: "crm_changes", label: "Изменение записей в CRM" },
  { id: "external_messages", label: "Сообщения в мессенджеры" },
] as const;
export type ConfirmAction = (typeof CONFIRM_ACTIONS)[number]["id"];

export type SafetyRules = {
  /** Applied top to bottom; disabled rules are kept but not sent. Empty rules are dropped on publish. */
  rules: GuardrailRule[];
  blocked_topics: string[];
  confirm_actions: ConfirmAction[];
};

export const RULE_MAX = 500;
export const RULES_LIMIT = 50;
export const TOPIC_MAX = 80;
export const TOPICS_LIMIT = 100;

/* ---------- Feature prompts ---------- */

export const FEATURES = [
  { id: "meeting_summary", label: "Саммари встречи", description: "Итоги звонка или записи: решения, задачи, сроки" },
  { id: "mind_map", label: "Майнд-карта", description: "Структура темы в виде дерева узлов" },
  { id: "email_draft", label: "Черновик письма", description: "Ответ или новое письмо в почте пользователя" },
  { id: "voice_mode", label: "Голосовой режим", description: "Короткие устные ответы без разметки" },
  { id: "agent_steps", label: "Агентские шаги", description: "План и вызовы инструментов: поиск, почта, календарь" },
] as const;
export type FeatureId = (typeof FEATURES)[number]["id"];

/** Added after the global system prompt while the feature runs; a disabled feature uses the global prompt only. */
export type FeaturePrompt = { content: string; enabled: boolean };

/* ---------- The whole configuration ---------- */

export const SYSTEM_PROMPT_MAX = 20_000;
export const FEATURE_PROMPT_MAX = 8_000;

/** Placeholders the backend fills in per request; anything else in `{{…}}` is sent as is. */
export const PLACEHOLDERS = [
  { key: "user_name", description: "Как Leo обращается к пользователю", example: "Анна" },
  { key: "language", description: "Язык ответа по политике", example: "русский" },
  { key: "date", description: "Сегодняшняя дата в часовом поясе пользователя", example: "5 октября 2026" },
  { key: "time", description: "Текущее время пользователя", example: "14:30" },
  { key: "workspace", description: "Название рабочего пространства", example: "Студия Север" },
  { key: "work_role", description: "Сфера работы из настроек", example: "Маркетинг" },
] as const;

export type PlatformPromptConfig = {
  system_prompt: string;
  behavior: BehaviorDefaults;
  safety: SafetyRules;
  features: Record<FeatureId, FeaturePrompt>;
};

/** PATCH /draft: any subset of sections; each section given replaces the stored one whole. */
export type PlatformPromptConfigPatch = Partial<PlatformPromptConfig>;

export type PlatformPromptDraft = {
  config: PlatformPromptConfig;
  updated_at: string;
  updated_by: string;
};

export type PlatformPromptVersion = {
  id: string;
  /** 1, 2, 3… in publishing order. */
  number: number;
  config: PlatformPromptConfig;
  comment: string;
  author: string;
  published_at: string;
  /** Set when this version was created by rolling back to an earlier one. */
  restored_from: number | null;
};

export type PlatformPromptsState = {
  draft: PlatformPromptDraft;
  /** The live version every user gets; null before the first publish. */
  published: PlatformPromptVersion | null;
  /** Newest first. */
  versions: PlatformPromptVersion[];
};

export const COMMENT_MAX = 280;

/** POST /publish. */
export type PublishRequest = { comment: string };
/** POST /versions/{id}/restore: publishes a copy of that version and resets the draft to it. */
export type RestoreRequest = { comment?: string };
