"use client";

import { createContext, use, useEffect, useState } from "react";

import { type StoreApi, useStore } from "zustand";
import { useShallow } from "zustand/react/shallow";

import {
  PREFERENCE_DEFAULTS,
  PREFERENCE_KEYS,
  PREFERENCE_REGISTRY,
  type PreferenceKey,
  type PreferenceValueMap,
  parsePreference,
} from "../domain/registry";
import type { SidebarPreferences } from "../domain/sidebar-preferences";
import { createPreferencesStore, type PreferencesState } from "./preferences-store";
import { applyThemeMode, subscribeToSystemTheme } from "./theme-mode";

const PreferencesStoreContext = createContext<StoreApi<PreferencesState> | null>(null);

function readDomPreference<K extends PreferenceKey>(key: K): PreferenceValueMap[K] {
  const definition = PREFERENCE_REGISTRY[key];
  const rawValue = document.documentElement.getAttribute(definition.attribute);

  return parsePreference(key, rawValue);
}

function readDomPreferences(): PreferenceValueMap {
  const values = { ...PREFERENCE_DEFAULTS };

  function assignPreference<K extends PreferenceKey>(key: K) {
    values[key] = readDomPreference(key);
  }

  for (const key of PREFERENCE_KEYS) assignPreference(key);
  return values;
}

export function PreferencesStoreProvider({
  children,
  initialValues,
}: {
  children: React.ReactNode;
  initialValues: PreferenceValueMap;
}) {
  const [store] = useState<StoreApi<PreferencesState>>(() => createPreferencesStore(initialValues));

  useEffect(() => {
    store.setState({
      values: readDomPreferences(),
      resolvedThemeMode: document.documentElement.classList.contains("dark") ? "dark" : "light",
      isSynced: true,
    });
  }, [store]);

  useEffect(() => {
    let unsubscribeMedia: (() => void) | undefined;

    const subscribeForMode = (mode: PreferenceValueMap["theme_mode"]) => {
      unsubscribeMedia?.();
      unsubscribeMedia = undefined;

      if (mode === "system") {
        unsubscribeMedia = subscribeToSystemTheme(() => {
          store.setState({ resolvedThemeMode: applyThemeMode("system") });
        });
      }
    };

    subscribeForMode(store.getState().values.theme_mode);

    const unsubscribeStore = store.subscribe((state, previousState) => {
      if (state.values.theme_mode !== previousState.values.theme_mode) {
        subscribeForMode(state.values.theme_mode);
      }
    });

    return () => {
      unsubscribeMedia?.();
      unsubscribeStore();
    };
  }, [store]);

  return <PreferencesStoreContext.Provider value={store}>{children}</PreferencesStoreContext.Provider>;
}

export function usePreferencesStore<T>(selector: (state: PreferencesState) => T): T {
  const store = use(PreferencesStoreContext) as StoreApi<PreferencesState> | null;
  if (!store) throw new Error("Missing PreferencesStoreProvider");
  return useStore(store, selector);
}

/**
 * The sidebar's variant and collapse mode once the store has read them from the page, `null` before that:
 * until then the sidebar keeps the values the server rendered with.
 */
export function useSidebarPreferences(): SidebarPreferences | null {
  return usePreferencesStore(
    useShallow((state) =>
      state.isSynced ? { variant: state.values.sidebar_variant, collapsible: state.values.sidebar_collapsible } : null,
    ),
  );
}
