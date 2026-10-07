import { PLACEHOLDERS } from "./contract";

const numberFormat = new Intl.NumberFormat("ru-RU");
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" });

export const formatNumber = (value: number) => numberFormat.format(value);
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso));

/** Rough token count for display only; the backend counts exactly. */
export const approxTokens = (text: string) => Math.ceil(text.length / 4);

const PLACEHOLDER_PATTERN = /\{\{\s*([\w.-]+)\s*\}\}/g;
const KNOWN_PLACEHOLDERS = new Set<string>(PLACEHOLDERS.map((placeholder) => placeholder.key));

/** `{{names}}` in the text that the backend won't fill in, each listed once. */
export function unknownPlaceholders(text: string) {
  const unknown = new Set<string>();
  for (const match of text.matchAll(PLACEHOLDER_PATTERN)) {
    if (!KNOWN_PLACEHOLDERS.has(match[1])) unknown.add(match[1]);
  }
  return [...unknown];
}

/** The prompt with every known placeholder replaced by its example value, for the preview. */
export const fillExamples = (text: string) =>
  text.replace(PLACEHOLDER_PATTERN, (token, key: string) => PLACEHOLDERS.find((p) => p.key === key)?.example ?? token);
