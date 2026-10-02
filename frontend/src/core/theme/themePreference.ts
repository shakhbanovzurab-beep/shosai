/**
 * Тема — привычка браузера: `wh.theme` на этом устройстве и `data-theme` на
 * `<html>`. Значения те же, что читает скрипт до первого кадра в index.html.
 */

import { readLocal, writeLocal } from "@/core/lib/browserStorage";

/** Выбор человека; «system» следует настройке системы на лету. */
export type ThemePreference = "light" | "dark" | "system";
/** Применённая тема — всегда светлая или тёмная. */
export type Theme = "light" | "dark";

const STORAGE_KEY = "wh.theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

/** Сохранённый выбор; незнакомое значение и недоступное хранилище дают светлую. */
export function readThemePreference(): ThemePreference {
  const stored = readLocal(STORAGE_KEY);
  return stored === "dark" || stored === "system" ? stored : "light";
}

export function storeThemePreference(preference: ThemePreference): void {
  writeLocal(STORAGE_KEY, preference);
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches;
}

export function resolveTheme(preference: ThemePreference): Theme {
  if (preference === "system") return systemPrefersDark() ? "dark" : "light";
  return preference;
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

/** Подписка на смену системной темы; возвращает отписку. */
export function watchSystemTheme(onChange: () => void): () => void {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
