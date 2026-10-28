import { z } from "zod";

import {
  FEATURE_PROMPT_MAX,
  RULE_ID_MAX,
  RULE_MAX,
  RULES_LIMIT,
  SYSTEM_PROMPT_MAX,
  TOPIC_MAX,
  TOPICS_LIMIT,
} from "./contract";

const featurePromptSchema = z.object({ content: z.string().max(FEATURE_PROMPT_MAX), enabled: z.boolean() });

/** Черновик, который сервер примет на сохранение: лимиты контракта; английский и бюджет проверяет публикация. */
export const configSchema = z.strictObject({
  system_prompt: z.string().max(SYSTEM_PROMPT_MAX, "Системный промт слишком длинный."),
  safety: z.object({
    rules: z
      .array(z.object({ id: z.string().min(1).max(RULE_ID_MAX), text: z.string().max(RULE_MAX), enabled: z.boolean() }))
      .max(RULES_LIMIT, `Не больше ${RULES_LIMIT} правил.`),
    blocked_topics: z.array(z.string().min(1).max(TOPIC_MAX)).max(TOPICS_LIMIT, `Не больше ${TOPICS_LIMIT} тем.`),
  }),
  features: z.object({ meeting_summary: featurePromptSchema, voice_mode: featurePromptSchema }),
});
