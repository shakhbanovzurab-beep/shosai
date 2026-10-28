import {
  FEATURE_TOKENS,
  FEATURES,
  type FeatureId,
  type FeaturePrompt,
  LAYER_TOKENS,
  type PlatformConfig,
} from "./contract";

/*
 * Зеркало `backend/src/shosai/features/studio/domain/platform_layer.py`: по нему экран заранее видит, что уйдёт
 * модели и сколько это стоит токенов. Решает сервер — при публикации он проверяет то же самое сам.
 */
const RULES_HEADING = "Platform rules, in order:";
const topicsLine = (topics: readonly string[]) =>
  `Decline politely to discuss the following topics, and do not search the web for them: ${topics.join("; ")}.`;
const BYTES_PER_TOKEN = 3;
const encoder = new TextEncoder();
const LETTER = /\p{L}/u;
const LATIN = /\p{Script=Latin}/u;

const OFF: FeaturePrompt = { content: "", enabled: false };

/** Конфигурация до первой публикации: встроенная политика Leo без слоя платформы. */
export const BUILT_IN: PlatformConfig = {
  system_prompt: "",
  safety: { rules: [], blocked_topics: [] },
  features: { meeting_summary: OFF, voice_mode: OFF },
};

export type Problem = { code: string; params: Readonly<Record<string, unknown>> };

/** Консервативная оценка токенов текста на любом языке — та же, что у сервера. */
export const estimateTokens = (text: string) => Math.ceil(encoder.encode(text).length / BYTES_PER_TOKEN);

/** Буквы не латиницей, без повторов: модель приняла бы такую инструкцию за просьбу отвечать на другом языке. */
export function nonLatinLetters(text: string): string[] {
  const found = new Set<string>();
  for (const char of text) if (LETTER.test(char) && !LATIN.test(char)) found.add(char);
  return [...found].toSorted();
}

/** Конфигурация в том виде, в каком публикуется: тексты без краевых пробелов, без пустых правил и повторов тем. */
export function cleaned(config: PlatformConfig): PlatformConfig {
  const topics = new Map<string, string>();
  for (const topic of config.safety.blocked_topics) {
    const text = topic.trim();
    if (text && !topics.has(text.toLowerCase())) topics.set(text.toLowerCase(), text);
  }
  const trimmed = (prompt: FeaturePrompt) => ({ ...prompt, content: prompt.content.trim() });
  return {
    system_prompt: config.system_prompt.trim(),
    safety: {
      rules: config.safety.rules
        .filter((rule) => rule.text.trim())
        .map((rule) => ({ ...rule, text: rule.text.trim() })),
      blocked_topics: [...topics.values()],
    },
    features: {
      meeting_summary: trimmed(config.features.meeting_summary),
      voice_mode: trimmed(config.features.voice_mode),
    },
  };
}

/** Текст слоя после политики Leo — из очищенной конфигурации; пустой, пока слоя нет. */
export function layerText(config: PlatformConfig): string {
  const parts = config.system_prompt ? [config.system_prompt] : [];
  const rules = config.safety.rules.filter((rule) => rule.enabled).map((rule) => `- ${rule.text}`);
  if (rules.length > 0) parts.push([RULES_HEADING, ...rules].join("\n"));
  if (config.safety.blocked_topics.length > 0) parts.push(topicsLine(config.safety.blocked_topics));
  return parts.join("\n\n");
}

/** Дополнение, которое берёт вызов функции; пустое, когда оно выключено. */
export function featureText(config: PlatformConfig, feature: FeatureId): string {
  const prompt = config.features[feature];
  return prompt.enabled ? prompt.content : "";
}

/** Каждый текст конфигурации, который читает модель, с полем, откуда он взят. */
function sentTexts(config: PlatformConfig): [string, string][] {
  return [
    ["system_prompt", config.system_prompt],
    ...config.safety.rules.flatMap((rule, index): [string, string][] =>
      rule.enabled ? [[`safety.rules.${index}`, rule.text]] : [],
    ),
    ...config.safety.blocked_topics.map((topic, index): [string, string] => [`safety.blocked_topics.${index}`, topic]),
    ...FEATURES.map(({ id }): [string, string] => [`features.${id}`, featureText(config, id)]),
  ];
}

/** Что помешает публикации черновика — первая причина в порядке сервера; null, если ничего. */
export function publishProblem(draft: PlatformConfig): Problem | null {
  const config = cleaned(draft);
  for (const [field, text] of sentTexts(config)) {
    if (nonLatinLetters(text).length > 0) return { code: "platform_prompt_not_english", params: { field } };
  }
  const tokens = estimateTokens(layerText(config));
  if (tokens > LAYER_TOKENS) {
    return { code: "platform_layer_over_budget", params: { field: "layer", tokens, max: LAYER_TOKENS } };
  }
  for (const { id } of FEATURES) {
    const featureTokens = estimateTokens(featureText(config, id));
    if (featureTokens > FEATURE_TOKENS) {
      return {
        code: "platform_layer_over_budget",
        params: { field: `features.${id}`, tokens: featureTokens, max: FEATURE_TOKENS },
      };
    }
  }
  return null;
}

/** Совпадают ли конфигурации так, как их сравнит сервер: после очистки. */
export function sameConfig(a: PlatformConfig, b: PlatformConfig): boolean {
  return JSON.stringify(canonical(cleaned(a))) === JSON.stringify(canonical(cleaned(b)));
}

// Порядок полей не важен: сравниваются значения.
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === "object") {
    return Object.entries(value)
      .toSorted(([a], [b]) => (a < b ? -1 : 1))
      .map(([key, item]) => [key, canonical(item)]);
  }
  return value;
}
