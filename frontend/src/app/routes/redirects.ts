import { type LoaderFunctionArgs, type RouteObject, redirect } from "react-router";

// Маршрут-редирект ничего не отрисовывает: loader уводит со страницы до отрисовки.
const NoContent = () => null;

/** Цель с добавленными параметрами запроса исходного адреса, как всегда делали редиректы кабинета. */
export function redirectTarget(requestUrl: string, target: string): string {
  const source = new URL(requestUrl);
  const destination = new URL(target, source.origin);
  for (const [key, value] of source.searchParams)
    if (!destination.searchParams.has(key)) destination.searchParams.append(key, value);
  return `${destination.pathname}${destination.search}`;
}

/** Маршрут, уводящий со своего адреса. Слайс, чей экран переехал, добавляет сюда старый адрес. */
export function redirectRoute(path: string, target: string): RouteObject {
  return {
    path,
    loader: ({ request }: LoaderFunctionArgs) => redirect(redirectTarget(request.url, target)),
    Component: NoContent,
  };
}

/** Старые адреса кабинета внутри /app и /admin: экраны, ставшие вкладками, и единственное командное пространство. */
export const legacyRedirects: RouteObject[] = [
  redirectRoute("/admin/analytics", "/admin/dashboard?tab=analytics"),
  redirectRoute("/admin/crm", "/admin/dashboard?tab=crm"),
  redirectRoute("/admin/crm-v1", "/admin/dashboard?tab=crm-v1"),
  redirectRoute("/app/studio/context", "/app/studio"),
  redirectRoute("/app/studio/prompts", "/app/studio?tab=prompts"),
  redirectRoute("/app/studio/models", "/app/studio?tab=models"),
  redirectRoute("/app/team", "/app/w"),
  redirectRoute("/app/team/*", "/app/w"),
];
