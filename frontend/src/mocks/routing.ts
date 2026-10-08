import { type HttpHandler, http } from "msw";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;
type Method = (typeof METHODS)[number];

type Handler = (request: Request, context: { params: Promise<Record<string, string>> }) => Response | Promise<Response>;

/** Один примерный путь и его обработчики вида `{ GET(request, { params }) { … } }`. */
export interface MockRoute {
  path: string;
  handlers: Partial<Record<Method, Handler>>;
}

const isMethod = (name: string): name is Method => (METHODS as readonly string[]).includes(name);

/** Примерный путь, который обслуживают заданные методы объекта-обработчика. */
export function mockRoute<R extends object>(path: string, route: R, methods: readonly (keyof R & string)[]): MockRoute {
  const handlers: Partial<Record<Method, Handler>> = {};
  for (const method of methods) {
    if (!isMethod(method)) throw new Error(`${path}: ${method} is not an HTTP method`);
    // Обработчики объявляют свои параметры пути точнее, чем Record<string, string>; MSW даёт их строками.
    handlers[method] = (route[method] as unknown as Handler).bind(route);
  }
  return { path, handlers };
}

const HTTP: Record<Method, typeof http.get> = {
  GET: http.get,
  POST: http.post,
  PUT: http.put,
  PATCH: http.patch,
  DELETE: http.delete,
};

/** Обработчики MSW для примерных маршрутов; параметры пути приходят в обработчик как `params`, как раньше. */
export function toHttpHandlers(routes: readonly MockRoute[]): HttpHandler[] {
  return routes.flatMap(({ path, handlers }) =>
    Object.entries(handlers).map(([method, handler]) =>
      HTTP[method as Method](path, ({ request, params }) =>
        handler(request, { params: Promise.resolve(params as Record<string, string>) }),
      ),
    ),
  );
}
