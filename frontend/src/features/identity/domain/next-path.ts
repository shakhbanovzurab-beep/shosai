/** Куда вернуть человека после входа: только страницы кабинета, никогда — чужой адрес или сами страницы входа. */

export const HOME_PATH = "/app";
export const LOGIN_PATH = "/app/login";

// Страницы входа и сброса пароля (а также прежние адреса регистрации): вернуть на них после входа значило бы
// пустить человека по кругу.
const AUTH_PATHS: readonly string[] = [LOGIN_PATH, "/app/register", "/app/forgot", "/app/reset"];

// Начало пути одной из панелей; `//host` и обратная косая — уже чужой адрес.
const PANEL_PATH = /^\/(app|admin)(\/|\?|#|$)/;

export function safeNext(raw: string | null | undefined): string {
  if (!raw || raw.includes("\\") || raw.startsWith("//") || !PANEL_PATH.test(raw)) return HOME_PATH;
  const path = raw.split(/[?#]/, 1)[0] ?? "";
  if (AUTH_PATHS.some((auth) => path === auth || path.startsWith(`${auth}/`))) return HOME_PATH;
  return raw;
}

/** Адрес входа, который вернёт человека на `next` после него. */
export function loginPathFor(next: string): string {
  const target = safeNext(next);
  return target === HOME_PATH ? LOGIN_PATH : `${LOGIN_PATH}?next=${encodeURIComponent(target)}`;
}
