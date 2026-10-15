/**
 * Адрес страницы входа в админку задаётся при сборке (`VITE_ADMIN_LOGIN_PATH`, ADR 0049) и нигде не показан:
 * `/admin/` и один сегмент из строчных латинских букв, цифр и дефисов, не короче 8 знаков, чтобы его не угадали
 * перебором коротких слов. Под /admin граница уже отдаёт кабинет, а без входа там всё отвечает «не найдено».
 * Без значения, с неверным или занятым экраном админки значением админка из кабинета недоступна.
 */
const LOGIN_PATH = /^\/admin\/([a-z0-9][a-z0-9-]{7,63})$/;

/** Адрес входа, если он верен и не совпадает с экраном админки (`taken` — их сегменты). */
export function adminLoginPathOf(value: string | undefined, taken: readonly string[]): string | null {
  const path = value?.trim() ?? "";
  const segment = LOGIN_PATH.exec(path)?.[1];
  return segment && !taken.includes(segment) ? path : null;
}

// Куда ведёт вход в админку: её главная страница.
export const ADMIN_HOME = "/admin/users";
