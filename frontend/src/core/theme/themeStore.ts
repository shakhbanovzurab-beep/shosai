/**
 * Состояние оформления: тема и роль шрифта.
 *
 * Общий стор у них потому, что оба нужны экрану «Внешний вид»; общего поля нет,
 * потому что срок жизни разный: тема — привычка браузера, шрифт — поле профиля.
 * Стор создаётся без побочных эффектов; документ и подписку на системную тему
 * поднимает явный вызов `startTheme()` в точке входа до первого рендера.
 */

import { create } from "zustand";

import { normalizeAppearance } from "@/core/theme/appearance";
import { applyAppearance, readStoredAppearance, storeAppearance } from "@/core/theme/appearanceDocument";
import { DEFAULT_FONT_ROLE, type FontRole } from "@/core/theme/fontCatalogue";
import {
  applyTheme,
  readThemePreference,
  resolveTheme,
  storeThemePreference,
  type Theme,
  type ThemePreference,
  watchSystemTheme,
} from "@/core/theme/themePreference";

export interface ThemeState {
  readonly pref: ThemePreference;
  /** Применённая тема; её читают все, кому нужен цвет. */
  readonly theme: Theme;
  readonly font: FontRole;
  readonly toggle: () => void;
  readonly setPref: (preference: ThemePreference) => void;
  readonly setFont: (font: FontRole) => void;
  /** Принять оформление из профиля, не отправляя его обратно на сервер. */
  readonly adoptServerAppearance: (incoming: unknown) => void;
}

/** Класс плавной смены цветов (core/styles/motion.css) и его срок на документе. */
const THEME_ANIMATION_CLASS = "theme-anim";
const THEME_ANIMATION_MS = 400;

/**
 * Пока сохранение шрифта в профиль в пути, ответ профиля может нести прежний
 * шрифт: принять его значило бы откатить выбор на глазах у человека.
 */
const ADOPT_QUIET_MS = 5000;

export const useThemeStore = create<ThemeState>()((set, get) => {
  let localEditAt = Number.NEGATIVE_INFINITY;
  let animationTimer: ReturnType<typeof setTimeout> | undefined;

  const switchTheme = (preference: ThemePreference): void => {
    const theme = resolveTheme(preference);
    const root = document.documentElement;
    root.classList.add(THEME_ANIMATION_CLASS);
    applyTheme(theme);
    storeThemePreference(preference);
    clearTimeout(animationTimer);
    animationTimer = setTimeout(() => root.classList.remove(THEME_ANIMATION_CLASS), THEME_ANIMATION_MS);
    set({ pref: preference, theme });
  };

  const commitFont = (font: FontRole): void => {
    applyAppearance({ font });
    storeAppearance({ font });
    set({ font });
  };

  return {
    pref: "light",
    theme: "light",
    font: DEFAULT_FONT_ROLE,
    toggle: () => switchTheme(get().theme === "dark" ? "light" : "dark"),
    setPref: switchTheme,
    setFont: (font) => {
      localEditAt = Date.now();
      commitFont(font);
    },
    adoptServerAppearance: (incoming) => {
      const { font } = normalizeAppearance(incoming);
      if (font === get().font || Date.now() - localEditAt < ADOPT_QUIET_MS) return;
      commitFont(font);
    },
  };
});

/**
 * Поднимает оформление из настроек этого устройства и следит за системной
 * темой, пока выбрана «Система». Атрибуты уже выставил скрипт в index.html;
 * повтор идемпотентен и нужен, если тот не отработал. Возвращает отписку.
 */
export function startTheme(): () => void {
  const pref = readThemePreference();
  const theme = resolveTheme(pref);
  const { font } = readStoredAppearance();
  applyTheme(theme);
  applyAppearance({ font });
  useThemeStore.setState({ pref, theme, font });
  return watchSystemTheme(() => {
    const state = useThemeStore.getState();
    if (state.pref === "system") state.setPref("system");
  });
}
