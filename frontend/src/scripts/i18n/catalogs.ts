import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** One catalog file: src/i18n/messages/<language>/<namespace>.json. */
export interface Catalog {
  path: string;
  lines: number;
  /** Every message by its full key, e.g. `weather.conditions.clear`. */
  messages: Map<string, string>;
  problems: string[];
}

// camelCase, or snake_case where a key is an API code (Leo's action ids).
const KEY = /^[a-z][a-zA-Z0-9_]*$/;
export const MAX_LINES = 200;

/** Flattens a catalog to `namespace.path.key` → message, noting anything next-intl can't use. */
export function flatten(value: unknown, prefix: string, into: Map<string, string>, problems: string[]) {
  if (typeof value === "string") {
    into.set(prefix, value);
    return;
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    problems.push(`${prefix}: must be a message or a group of messages`);
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    if (!KEY.test(key))
      problems.push(`${prefix}.${key}: keys are camelCase (or snake_case codes): letters, digits and _`);
    flatten(child, `${prefix}.${key}`, into, problems);
  }
}

export function readCatalog(path: string, namespace: string): Catalog {
  const text = readFileSync(path, "utf8");
  const catalog: Catalog = { path, lines: text.split("\n").length - 1, messages: new Map(), problems: [] };
  if (catalog.lines > MAX_LINES) catalog.problems.push(`${catalog.lines} lines, over the ${MAX_LINES}-line limit`);
  try {
    flatten(JSON.parse(text), namespace, catalog.messages, catalog.problems);
  } catch (error) {
    catalog.problems.push(`isn’t valid JSON (${error instanceof Error ? error.message : error})`);
  }
  return catalog;
}

/** Every catalog of one language, by namespace; null when the language has no folder. */
export function readLanguage(root: string, language: string): Map<string, Catalog> | null {
  const folder = join(root, language);
  if (!existsSync(folder)) return null;
  const catalogs = new Map<string, Catalog>();
  for (const file of readdirSync(folder)
    .filter((name) => name.endsWith(".json"))
    .sort()) {
    const namespace = file.slice(0, -".json".length);
    catalogs.set(namespace, readCatalog(join(folder, file), namespace));
  }
  return catalogs;
}

/** Namespaces and keys a language has that English hasn't, and the other way round. */
export function compareKeys(english: Map<string, Catalog>, other: Map<string, Catalog>): string[] {
  const problems: string[] = [];
  for (const [namespace, catalog] of english) {
    const theirs = other.get(namespace);
    if (!theirs) {
      problems.push(`lacks ${namespace}.json`);
      continue;
    }
    for (const key of catalog.messages.keys()) if (!theirs.messages.has(key)) problems.push(`${key}: missing`);
    for (const key of theirs.messages.keys()) if (!catalog.messages.has(key)) problems.push(`${key}: not in English`);
  }
  for (const namespace of other.keys()) if (!english.has(namespace)) problems.push(`${namespace}.json: not in English`);
  return problems;
}
