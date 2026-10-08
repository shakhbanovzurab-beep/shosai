import type { RouteObject } from "react-router";

/**
 * Маршрут, модуль которого (`Component`, и `loader`, если есть) — отдельный чанк, загружаемый при первом
 * посещении. Таблицы маршрутов импортируют модули страниц по пути, поэтому чанки остаются постраничными.
 */
export const page = (load: () => Promise<object>): Pick<RouteObject, "lazy"> => ({ lazy: load });

type LoaderModule = { loader: NonNullable<RouteObject["loader"]> };
type ComponentModule = { Component: NonNullable<RouteObject["Component"]> };

/**
 * Страница с данными: модуль loader-а и модуль компонента — отдельные чанки, и роутер загружает их
 * параллельно, так что запрос данных не ждёт кода страницы.
 */
export const pageWithData = (
  loadLoader: () => Promise<LoaderModule>,
  loadComponent: () => Promise<ComponentModule>,
): Pick<RouteObject, "lazy"> => ({
  lazy: {
    loader: async () => (await loadLoader()).loader,
    Component: async () => (await loadComponent()).Component,
  },
});
