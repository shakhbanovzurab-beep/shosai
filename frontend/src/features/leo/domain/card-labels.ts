/*
 * Коды карточки, которые кабинет пишет словами: метка внешнего текста, прочитанного до неё (Leo §7.4), и код
 * неудачи пункта действия. Набор закрыт на сервере; незнакомая метка — общие слова, незнакомый код — без слов:
 * статус карточки и так говорит, что не вышло.
 */

const TAINTS = {
  mail: "mail",
  web: "web",
  "file:foreign": "fileForeign",
  "file:own": "fileOwn",
  "meeting:speech": "meetingSpeech",
  "task:foreign": "taskForeign",
  memory: "memory",
  "skill:user": "skillUser",
} as const;

export type TaintKey = (typeof TAINTS)[keyof typeof TAINTS] | "mcp" | "other";

const MCP = "mcp:";

const isTaint = (label: string): label is keyof typeof TAINTS => Object.hasOwn(TAINTS, label);

/** Ключ слов метки и, для внешнего MCP-сервера, его имя. */
export function taintOf(label: string): { key: TaintKey; server?: string } {
  if (label.startsWith(MCP)) return { key: "mcp", server: label.slice(MCP.length) };
  return { key: isTaint(label) ? TAINTS[label] : "other" };
}

const OUTCOMES = [
  "invalid_arguments",
  "not_found",
  "forbidden",
  "not_entitled",
  "limit_reached",
  "switched_off",
  "conflict",
  "timeout",
  "unavailable",
  "rate_limited",
  "failed",
  "not_started",
  "executor_lost",
] as const;

export type OutcomeCode = (typeof OUTCOMES)[number];

const KNOWN: ReadonlySet<string> = new Set(OUTCOMES);

const isOutcome = (code: string): code is OutcomeCode => KNOWN.has(code);

/** Код неудачи, у которого есть слова; иначе null. */
export const outcomeOf = (code: string | null): OutcomeCode | null => (code !== null && isOutcome(code) ? code : null);
