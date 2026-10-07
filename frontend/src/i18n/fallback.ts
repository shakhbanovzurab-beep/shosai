type Tree = { [key: string]: string | Tree };

/**
 * A translation laid over the English messages: anything the translation lacks shows in English instead of
 * as a raw key. `npm run i18n:check` keeps every language complete; this only guards a release against a gap.
 */
export function withFallback<T extends Tree>(english: T, translation: Tree): T {
  const merged: Tree = { ...english };
  for (const [key, value] of Object.entries(translation)) {
    const base = english[key];
    if (typeof value === "string") {
      if (typeof base === "string" && value.trim()) merged[key] = value;
    } else if (base !== undefined && typeof base !== "string") {
      merged[key] = withFallback(base, value);
    }
  }
  return merged as T;
}
