import { createBrowserRouter, type RouteObject } from "react-router";

import { NotFoundPage } from "./errors/not-found-page";
import { RootError } from "./errors/root-error";
import { RouteError } from "./errors/route-error";
import { SignedInLayout } from "./layouts/signed-in";
import { RootLayout } from "./root/root-layout";
import { revalidateRoot, rootLoader } from "./root/root-loader";
import { adminPanelRoutes } from "./routes/admin-panel";
import { adminGuard, signedInGuard } from "./routes/guards";
import { legacyRedirects } from "./routes/redirects";
import { standaloneRoutes } from "./routes/standalone";
import { userPanelRoutes } from "./routes/user-panel";

/**
 * Маршруты кабинета: корень загружает язык страницы, маршрут без пути ловит ошибки страниц внутри провайдеров,
 * охрана пускает в панель /app только вошедшего, в админку — только администратора, таблицы панелей держат страницы. `extraRoutes` — страницы только для разработки, их регистрируют моки
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
            { loader: signedInGuard, Component: SignedInLayout, children: userPanelRoutes },
            { loader: adminGuard, children: adminPanelRoutes },
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
