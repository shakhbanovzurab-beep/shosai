import { createBrowserRouter, type RouteObject } from "react-router";

import { NotFoundPage } from "./errors/not-found-page";
import { RootError } from "./errors/root-error";
import { RouteError } from "./errors/route-error";
import { RootLayout } from "./root/root-layout";
import { revalidateRoot, rootLoader } from "./root/root-loader";
import { adminPanelRoutes } from "./routes/admin-panel";
import { legacyRedirects } from "./routes/redirects";
import { standaloneRoutes } from "./routes/standalone";
import { userPanelRoutes } from "./routes/user-panel";

/**
 * Маршруты кабинета: корень загружает язык страницы, маршрут без пути ловит ошибки страниц внутри провайдеров,
 * таблицы панелей держат страницы. `extraRoutes` — страницы только для разработки, их регистрируют моки
 * (src/mocks); в production-сборку они не попадают.
 */
export function createRouter(extraRoutes: RouteObject[] = []) {
  return createBrowserRouter([
    {
      id: "root",
      path: "/",
      loader: rootLoader,
      shouldRevalidate: revalidateRoot,
      Component: RootLayout,
      HydrateFallback: () => null,
      ErrorBoundary: RootError,
      children: [
        {
          ErrorBoundary: RouteError,
          children: [
            ...userPanelRoutes,
            ...adminPanelRoutes,
            ...standaloneRoutes,
            ...legacyRedirects,
            ...extraRoutes,
            { path: "*", Component: NotFoundPage },
          ],
        },
      ],
    },
  ]);
}
