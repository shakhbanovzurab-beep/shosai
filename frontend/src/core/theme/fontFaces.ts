/**
 * Объявления `@font-face` подключаются по паре «язык × роль» (спека 084):
 * все вместе весят 3 МБ, а нужна одна пара. До первого кадра её подключает
 * скрипт в index.html, на живой странице — этот модуль: при смене роли или
 * языка и для плиток выбора шрифта.
 *
 * Своего реестра подключённого нет: источник правды — сам документ.
 */

import type { FontRole } from "@/core/theme/fontCatalogue";

/** Адрес файла объявлений. `lang` — значение `<html lang>` (`zh-Hant`, не `zh`). */
export function fontFacesHref(lang: string, role: FontRole): string {
  return `/fonts/roles-${lang}-${role}.css`;
}

/** Подключает объявления пары, если их ещё нет в документе. */
export function ensureFontFaces(lang: string, role: FontRole): void {
  if (lang === "") return;
  const href = fontFacesHref(lang, role);
  const present = [...document.head.querySelectorAll('link[rel="stylesheet"]')].some(
    (link) => link.getAttribute("href") === href,
  );
  if (present) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  // Несостоявшаяся загрузка не оставляет мёртвую ссылку: следующая попытка
  // подключить ту же пару пройдёт заново.
  link.addEventListener("error", () => link.remove(), { once: true });
  document.head.append(link);
}
