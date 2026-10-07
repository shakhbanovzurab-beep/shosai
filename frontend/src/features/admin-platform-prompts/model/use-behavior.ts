"use client";

import type { BehaviorDefaults } from "../domain/contract";
import { usePlatformPrompts } from "./platform-prompts-provider";

export function useBehavior() {
  const {
    state: { config },
    actions: { update },
  } = usePlatformPrompts();
  const set = (patch: Partial<BehaviorDefaults>) =>
    update((current) => ({ ...current, behavior: { ...current.behavior, ...patch } }));
  return { behavior: config.behavior, set };
}
