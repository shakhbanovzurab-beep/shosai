import { createStore } from "zustand/vanilla";

import type { ResolvedThemeMode } from "@/lib/preferences/theme";

import { PREFERENCE_DEFAULTS, PREFERENCE_KEYS, type PreferenceKey, type PreferenceValueMap } from "../domain/registry";
import { applyPreference } from "./apply-preference";
import { persistPreference } from "./persist-preference";

export type PreferencesState = {
  values: PreferenceValueMap;
  resolvedThemeMode: ResolvedThemeMode;
  isSynced: boolean;
  setPreference: <K extends PreferenceKey>(key: K, value: PreferenceValueMap[K]) => void;
  resetPreferences: () => void;
};

export const createPreferencesStore = (initialValues: Partial<PreferenceValueMap> = {}) => {
  const values: PreferenceValueMap = {
    ...PREFERENCE_DEFAULTS,
    ...initialValues,
  };

  return createStore<PreferencesState>()((set) => ({
    values,
    resolvedThemeMode: values.theme_mode === "dark" ? "dark" : "light",
    isSynced: false,

    setPreference: (key, value) => {
      const resolvedThemeMode = applyPreference(key, value);

      set((state) => ({
        values: {
          ...state.values,
          [key]: value,
        } as PreferenceValueMap,
        ...(resolvedThemeMode ? { resolvedThemeMode } : {}),
      }));

      void persistPreference(key, value);
    },

    resetPreferences: () => {
      let resolvedThemeMode: ResolvedThemeMode = "light";

      for (const key of PREFERENCE_KEYS) {
        const value = PREFERENCE_DEFAULTS[key];
        const resolved = applyPreference(key, value);

        if (resolved) resolvedThemeMode = resolved;
        void persistPreference(key, value);
      }

      set({
        values: { ...PREFERENCE_DEFAULTS },
        resolvedThemeMode,
      });
    },
  }));
};
