"use client";

import { setClientCookie } from "@/lib/cookie.client";
import { setLocalStorageValue } from "@/lib/local-storage.client";

import {
  getPreferencePersistence,
  type PreferenceKey,
  type PreferencePersistence,
  type PreferenceValueMap,
} from "../domain/registry";
import { setPreferenceCookie } from "../server/preference-actions";

async function persistByMode(mode: PreferencePersistence, key: PreferenceKey, value: string): Promise<void> {
  switch (mode) {
    case "none":
      return;

    case "client-cookie":
      setClientCookie(key, value);
      return;

    case "server-cookie":
      await setPreferenceCookie(key, value);
      return;

    case "localStorage":
      setLocalStorageValue(key, value);
      return;
  }
}

export function persistPreference<K extends PreferenceKey>(key: K, value: PreferenceValueMap[K]): Promise<void> {
  return persistByMode(getPreferencePersistence(key), key, value);
}
