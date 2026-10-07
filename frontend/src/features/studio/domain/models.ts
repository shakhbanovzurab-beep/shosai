import type { ModelInfo } from "./contract";

/** Models grouped by provider, providers and models alphabetically. */
export function byProvider(models: ModelInfo[]) {
  const groups = new Map<string, ModelInfo[]>();
  for (const model of models.toSorted((a, b) => a.name.localeCompare(b.name))) {
    groups.set(model.provider, [...(groups.get(model.provider) ?? []), model]);
  }
  return [...groups.entries()].toSorted(([a], [b]) => a.localeCompare(b));
}

/** Rough token count for display only; the backend counts exactly. */
export const approxTokens = (text: string) => Math.ceil(text.length / 4);
