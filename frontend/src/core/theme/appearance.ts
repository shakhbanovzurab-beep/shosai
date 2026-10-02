/**
 * Оформление, которое синхронизируется через профиль: сейчас это роль шрифта.
 *
 * Чистый модуль — ни DOM, ни хранилища. Тема (светлая, тёмная, системная)
 * сюда не входит: она привычка браузера и живёт в `wh.theme`, а оформление —
 * поле профиля и доезжает до второго устройства. Разный срок жизни — разные
 * механизмы.
 */

import { DEFAULT_FONT_ROLE, FONT_ROLES, type FontRole } from "@/core/theme/fontCatalogue";

export interface Appearance {
  readonly font: FontRole;
}

/** Фирменный набор; совпадает со значением сервера по умолчанию. */
export const DEFAULT_APPEARANCE: Appearance = { font: DEFAULT_FONT_ROLE };

/** Прежние имена вариантов (до спеки 084): человек выбирал руками, выбор сохраняется. */
const LEGACY_FONT_NAMES: ReadonlyMap<string, FontRole> = new Map([
  ["alt", "sans"],
  ["system", "native"],
]);

const isFontRole = (value: string): value is FontRole =>
  (FONT_ROLES as readonly string[]).includes(value);

/**
 * Любой вход — ответ сервера, localStorage, след прежней версии — даёт рабочее
 * оформление. Непонятое значение заменяется фирменным, а не роняет разбор:
 * повреждённая настройка не должна стоить человеку пустого экрана.
 */
export function normalizeAppearance(input: unknown): Appearance {
  const font = typeof input === "object" && input !== null ? Reflect.get(input, "font") : undefined;
  if (typeof font !== "string") return DEFAULT_APPEARANCE;
  if (isFontRole(font)) return { font };
  return { font: LEGACY_FONT_NAMES.get(font) ?? DEFAULT_APPEARANCE.font };
}
