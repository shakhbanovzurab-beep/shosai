import { isRouteErrorResponse, useRouteError } from "react-router";

import { NotFoundPage } from "./not-found-page";
import { RootError } from "./root-error";

/** Что страница показывает вместо себя: «не найдено» для 404 (неизвестный адрес или id), иначе страницу сбоя. */
export function RouteError() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFoundPage />;
  return <RootError />;
}
