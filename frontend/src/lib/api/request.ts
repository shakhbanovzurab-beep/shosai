import { apiErrorOf } from "./errors";
import { interfaceLanguage } from "./interface-language";

/**
 * Получает JSON из API на этом же origin; при сбое бросает ApiError. Бэкенд пишет ошибки и новые данные на
 * языке интерфейса, который получает в `Accept-Language`.
 */
export async function apiRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("accept-language")) headers.set("accept-language", interfaceLanguage());
  const response = await fetch(url, { cache: "no-store", credentials: "same-origin", ...init, headers });
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw apiErrorOf(response.status, body, response.headers);
  return body as T;
}

/** Тело запроса в JSON с соответствующим типом содержимого. */
export const jsonBody = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "content-type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});
