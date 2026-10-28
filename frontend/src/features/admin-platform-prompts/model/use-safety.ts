"use client";

import type { SafetyRules } from "../domain/contract";
import { usePlatformPrompts } from "./platform-prompts-provider";

/** Правила и запрещённые темы черновика с заменой части раздела. */
export function useSafety() {
  const {
    state: { config },
    actions: { update },
  } = usePlatformPrompts();
  const set = (change: (safety: SafetyRules) => Partial<SafetyRules>) =>
    update((current) => ({ ...current, safety: { ...current.safety, ...change(current.safety) } }));
  return { safety: config.safety, set };
}
