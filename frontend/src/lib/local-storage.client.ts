"use client";

export function setLocalStorageValue(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    if (import.meta.env.DEV) {
      console.error("[localStorage] Failed to write value:", error);
    }
  }
}
