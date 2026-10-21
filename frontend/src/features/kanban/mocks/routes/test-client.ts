/* Вызов маршрута моков в тестах без MSW: тот же Request, те же параметры пути. */

type Handler = (request: Request, context: { params: Promise<Record<string, string>> }) => Promise<Response>;
type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type Reply = { status: number; body: unknown };

export async function call(
  route: object,
  method: Method,
  path: string,
  options: { body?: unknown; params?: Record<string, string>; headers?: Record<string, string> } = {},
): Promise<Reply> {
  const handler = (route as Record<string, unknown>)[method] as Handler;
  const request = new Request(`http://demo.test${path}`, {
    method,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    headers: { "content-type": "application/json", ...options.headers },
  });
  const response = await handler.call(route, request, { params: Promise.resolve(options.params ?? {}) });
  return { status: response.status, body: response.status === 204 ? null : await response.json() };
}

/** Код отказа из конверта ADR 0008. */
export const codeOf = (reply: Reply) => (reply.body as { error?: { code?: string } } | null)?.error?.code ?? null;
