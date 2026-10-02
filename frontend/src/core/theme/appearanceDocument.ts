/**
 * Оформление на документе и его память на этом устройстве.
 *
 * Документ знает о шрифте ровно один атрибут — `data-font` на `<html>`; в
 * семейства его разворачивают правила `core/styles/generated/font-roles.css`.
 * Фирменная роль атрибут СНИМАЕТ: без него не совпадает ни одно правило
 * выбора, и человек, который ничего не настраивал, видит фирменный Whisperer.
 */

import { readLocal, writeLocal } from "@/core/lib/browserStorage";
import { type Appearance, DEFAULT_APPEARANCE, normalizeAppearance } from "@/core/theme/appearance";
import { ensureFontFaces } from "@/core/theme/fontFaces";

/**
 * Кэш выбора до первого ответа профиля. Версии в ключе нет: любой вход проходит
 * через `normalizeAppearance`, который незнакомое заменяет фирменным, — версия
 * при смене формы только отобрала бы у человека выбранный шрифт.
 */
const STORAGE_KEY = "wh.appearance";

/** Выбор, сохранённый на этом устройстве, или фирменный. */
export function readStoredAppearance(): Appearance {
  const raw = readLocal(STORAGE_KEY);
  if (raw === null) return DEFAULT_APPEARANCE;
  try {
    return normalizeAppearance(JSON.parse(raw));
  } catch {
    // Битый JSON — фирменное оформление, как у нового человека.
    return DEFAULT_APPEARANCE;
  }
}

/** Запоминает выбор; без хранилища он действует до перезагрузки и всё равно лежит в профиле. */
export function storeAppearance(appearance: Appearance): void {
  writeLocal(STORAGE_KEY, JSON.stringify(appearance));
}

/** Ставит роль на `<html>` и подключает её объявления `@font-face` для текущего языка. */
export function applyAppearance(appearance: Appearance): void {
  const root = document.documentElement;
  if (appearance.font === DEFAULT_APPEARANCE.font) root.removeAttribute("data-font");
  else root.setAttribute("data-font", appearance.font);
  ensureFontFaces(root.lang, appearance.font);
}
