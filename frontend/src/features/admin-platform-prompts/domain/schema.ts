import { z } from "zod";

import {
  COMMENT_MAX,
  CONFIRM_ACTIONS,
  FEATURE_PROMPT_MAX,
  FEATURES,
  OUTPUT_TOKENS_MAX,
  OUTPUT_TOKENS_MIN,
  OVERRIDABLE_SETTINGS,
  RULE_MAX,
  RULES_LIMIT,
  SYSTEM_PROMPT_MAX,
  TEMPERATURE_MAX,
  TEMPERATURE_MIN,
  TONES,
  TOPIC_MAX,
  TOPICS_LIMIT,
} from "./contract";

const ids = <T extends readonly { id: string }[]>(items: T) =>
  items.map((item) => item.id) as unknown as [T[number]["id"], ...T[number]["id"][]];

const behaviorSchema = z.object({
  tone: z.enum(ids(TONES)),
  language_policy: z.enum(["user", "fixed"]),
  fixed_language: z.string().trim().min(2).max(16),
  default_model: z.string().trim().min(1, "Укажите модель по умолчанию.").max(120),
  temperature: z.number().min(TEMPERATURE_MIN).max(TEMPERATURE_MAX),
  max_output_tokens: z.number().int().min(OUTPUT_TOKENS_MIN).max(OUTPUT_TOKENS_MAX),
  web_search: z.boolean(),
  user_overrides: z.array(z.enum(ids(OVERRIDABLE_SETTINGS))),
});

const safetySchema = z.object({
  rules: z
    .array(z.object({ id: z.string().min(1).max(64), text: z.string().max(RULE_MAX), enabled: z.boolean() }))
    .max(RULES_LIMIT, `Не больше ${RULES_LIMIT} правил.`),
  blocked_topics: z.array(z.string().trim().min(1).max(TOPIC_MAX)).max(TOPICS_LIMIT),
  confirm_actions: z.array(z.enum(ids(CONFIRM_ACTIONS))),
});

const featurePromptSchema = z.object({ content: z.string().max(FEATURE_PROMPT_MAX), enabled: z.boolean() });

const featuresSchema = z.object(
  Object.fromEntries(FEATURES.map((feature) => [feature.id, featurePromptSchema])) as Record<
    (typeof FEATURES)[number]["id"],
    typeof featurePromptSchema
  >,
);

export const configPatchSchema = z
  .object({
    system_prompt: z.string().max(SYSTEM_PROMPT_MAX, "Системный промт слишком длинный."),
    behavior: behaviorSchema,
    safety: safetySchema,
    features: featuresSchema,
  })
  .partial()
  .strict();

export const publishSchema = z.object({
  comment: z.string().trim().min(1, "Опишите, что изменилось.").max(COMMENT_MAX),
});

export const restoreSchema = z.object({ comment: z.string().trim().max(COMMENT_MAX).optional() });
