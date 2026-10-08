import createClient, { type Client, type Middleware } from "openapi-fetch";

import { apiErrorOf } from "./errors";
import type { paths } from "./generated/schema";
import { interfaceLanguage } from "./interface-language";

/** Клиент API бэкенда по его контракту OpenAPI (backend/openapi.json → generated/schema.d.ts). */
export type ApiClient = Client<paths>;

// Язык интерфейса уходит на бэкенд, чтобы ошибки и новые данные были на нём (админка — русская).
const interfaceLanguageHeader: Middleware = {
  onRequest({ request }) {
    if (!request.headers.has("accept-language")) request.headers.set("accept-language", interfaceLanguage());
    return request;
  },
};

/**
 * Клиент на том же origin, что и кабинет; `baseUrl` нужен только тестам. Промежуточные обработчики слайсов
 * (S01 — CSRF и обновление сессии) подключаются через `client.use(...)` в точке сборки приложения.
 */
export function createApiClient(baseUrl = ""): ApiClient {
  const client = createClient<paths>({ baseUrl, credentials: "same-origin" });
  client.use(interfaceLanguageHeader);
  return client;
}

/** Ответ метода клиента без ошибки или ApiError по конверту ADR 0008 — для запросов TanStack Query. */
export async function dataOf<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || !response.ok) throw apiErrorOf(response.status, error ?? null, response.headers);
  return data as T;
}
