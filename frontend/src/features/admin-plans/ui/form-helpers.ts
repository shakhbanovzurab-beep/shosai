import type { z } from "zod";

import { issuesByField } from "../domain/schema";

/** The record without `key` (same object when absent, so state doesn't change needlessly). */
export function withoutKey(record: Record<string, string>, key: string): Record<string, string> {
  if (!(key in record)) return record;
  return Object.fromEntries(Object.entries(record).filter(([name]) => name !== key));
}

/** One message per form field, mapping validation paths to field keys with `keyOf`. */
export function errorsByKey(error: z.ZodError, keyOf: (path: string) => string): Record<string, string> {
  const found: Record<string, string> = {};
  for (const [path, message] of Object.entries(issuesByField(error))) {
    const key = keyOf(path);
    if (!(key in found)) found[key] = message;
  }
  return found;
}

/** Moves focus to the first invalid control so keyboard and screen-reader users land on the problem. */
export function focusFirst(errors: Record<string, string>, idOf: (key: string) => string) {
  const first = Object.keys(errors)[0];
  if (first) document.getElementById(idOf(first))?.focus();
}
