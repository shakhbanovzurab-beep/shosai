/**
 * Вход десктоп-приложения через браузер (ADR 0045): приложение открывает `/app/connect?state=…[&code_challenge=…]`,
 * вошедший человек подтверждает, страница получает одноразовый код и возвращает браузер в приложение по схеме
 * `shosai://auth`.
 */
export const DESKTOP_SCHEME_URL = "shosai://auth";

export interface DesktopRequest {
  state: string;
  codeChallenge: string | null;
}

/** Запрос приложения из адреса страницы; без `state` приложение не узнает свой ответ — такой запрос негоден. */
export function desktopRequestOf(params: URLSearchParams): DesktopRequest | null {
  const state = params.get("state");
  if (!state) return null;
  return { state, codeChallenge: params.get("code_challenge") || null };
}

/** Адрес возврата в приложение с кодом и тем же `state`. */
export function desktopReturnUrl(code: string, state: string): string {
  return `${DESKTOP_SCHEME_URL}?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`;
}
