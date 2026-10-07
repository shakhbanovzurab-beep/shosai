"use client";

import type { SafetyRules } from "../domain/contract";
import { usePlatformPrompts } from "./platform-prompts-provider";

export function useSafety() {
  const {
    state: { config },
    actions: { update },
  } = usePlatformPrompts();
  const set = (change: (safety: SafetyRules) => Partial<SafetyRules>) =>
    update((current) => ({ ...current, safety: { ...current.safety, ...change(current.safety) } }));
  return { safety: config.safety, set };
}
