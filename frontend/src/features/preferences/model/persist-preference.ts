import { setClientCookie } from "@/lib/cookie.client";
import { setLocalStorageValue } from "@/lib/local-storage.client";

import {
  getPreferencePersistence,
  type PreferenceKey,
  type PreferencePersistence,
  type PreferenceValueMap,
} from "../domain/registry";

function persistByMode(mode: PreferencePersistence, key: PreferenceKey, value: string): void {
  switch (mode) {
    case "none":
      return;

    case "client-cookie":
      setClientCookie(key, value);
      return;

    case "localStorage":
      setLocalStorageValue(key, value);
      return;
  }
}

export function persistPreference<K extends PreferenceKey>(key: K, value: PreferenceValueMap[K]): Promise<void> {
  persistByMode(getPreferencePersistence(key), key, value);
  return Promise.resolve();
}
