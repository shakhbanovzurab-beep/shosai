import { LANGUAGES } from "@/lib/language";

import { CONFIRM_ACTIONS, FEATURES, OVERRIDABLE_SETTINGS, type PlatformPromptConfig, TONES } from "./contract";

/** JSON with sorted keys, so two configs compare equal whatever order their fields arrived in. */
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value).toSorted(([a], [b]) => (a < b ? -1 : 1));
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export const sameConfig = (a: PlatformPromptConfig, b: PlatformPromptConfig | null | undefined) =>
  b != null && canonical(a) === canonical(b);

const labelOf = <T extends { id: string; label: string }>(items: readonly T[], id: string) =>
  items.find((item) => item.id === id)?.label ?? id;

const onOff = (enabled: boolean) => (enabled ? "вкл." : "выкл.");

/** A readable plain-text rendering of a config, one fact per line, for the side-by-side comparison. */
export function configToText(config: PlatformPromptConfig): string[] {
  const { behavior, safety } = config;
  const language =
    behavior.language_policy === "user"
      ? "язык пользователя"
      : `фиксированный — ${LANGUAGES.find((l) => l.code === behavior.fixed_language)?.label ?? behavior.fixed_language}`;
  const lines = [
    "## Системный промт",
    ...config.system_prompt.split("\n"),
    "",
    "## Поведение",
    `Стиль ответов: ${labelOf(TONES, behavior.tone)}`,
    `Язык ответов: ${language}`,
    `Модель: ${behavior.default_model}`,
    `Температура: ${behavior.temperature}`,
    `Макс. токенов ответа: ${behavior.max_output_tokens}`,
    `Веб-поиск: ${onOff(behavior.web_search)}`,
    `Пользователи могут менять: ${
      behavior.user_overrides.map((id) => labelOf(OVERRIDABLE_SETTINGS, id)).join(", ") || "ничего"
    }`,
    "",
    "## Правила безопасности",
    ...safety.rules.map((rule, index) => `${index + 1}. [${onOff(rule.enabled)}] ${rule.text}`),
    "",
    "## Запрещённые темы",
    ...safety.blocked_topics.map((topic) => `- ${topic}`),
    "",
    "## Требуют подтверждения",
    ...safety.confirm_actions.map((id) => `- ${labelOf(CONFIRM_ACTIONS, id)}`),
  ];
  for (const feature of FEATURES) {
    const prompt = config.features[feature.id];
    lines.push("", `## Функция «${feature.label}» (${onOff(prompt.enabled)})`, ...prompt.content.split("\n"));
  }
  return lines;
}

export type DiffRow =
  | { kind: "same"; left: string; right: string }
  | { kind: "changed"; left: string | null; right: string | null };

const MAX_CELLS = 4_000_000;

/**
 * Line diff (longest common subsequence) laid out side by side: unchanged lines face each other,
 * and each run of removals is paired row by row with the run of additions that replaces it.
 */
export function diffLines(left: string[], right: string[]): DiffRow[] {
  const n = left.length;
  const m = right.length;
  if (n * m > MAX_CELLS) return pairRuns(left, right);

  // lcs[i][j] = LCS length of left[i..] and right[j..], flattened.
  const width = m + 1;
  const lcs = new Uint32Array((n + 1) * width);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i * width + j] =
        left[i] === right[j]
          ? lcs[(i + 1) * width + j + 1] + 1
          : Math.max(lcs[(i + 1) * width + j], lcs[i * width + j + 1]);
    }
  }

  const rows: DiffRow[] = [];
  let removed: string[] = [];
  let added: string[] = [];
  const flush = () => {
    rows.push(...pairRuns(removed, added));
    removed = [];
    added = [];
  };
  let i = 0;
  let j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && left[i] === right[j]) {
      flush();
      rows.push({ kind: "same", left: left[i], right: right[j] });
      i++;
      j++;
    } else if (j < m && (i === n || lcs[i * width + j + 1] >= lcs[(i + 1) * width + j])) {
      added.push(right[j++]);
    } else {
      removed.push(left[i++]);
    }
  }
  flush();
  return rows;
}

function pairRuns(removed: string[], added: string[]): DiffRow[] {
  return Array.from({ length: Math.max(removed.length, added.length) }, (_, index) => ({
    kind: "changed" as const,
    left: removed[index] ?? null,
    right: added[index] ?? null,
  }));
}
