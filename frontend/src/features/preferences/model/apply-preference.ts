"use client";

import type { ResolvedThemeMode } from "@/lib/preferences/theme";

import { PREFERENCE_REGISTRY, type PreferenceKey, type PreferenceValueMap } from "../domain/registry";
import { applyThemeMode } from "./theme-mode";

export function applyPreference<K extends PreferenceKey>(
  key: K,
  value: PreferenceValueMap[K],
): ResolvedThemeMode | undefined {
  if (key === "theme_mode") {
    return applyThemeMode(value as PreferenceValueMap["theme_mode"]);
  }

  document.documentElement.setAttribute(PREFERENCE_REGISTRY[key].attribute, value);
  return undefined;
}
