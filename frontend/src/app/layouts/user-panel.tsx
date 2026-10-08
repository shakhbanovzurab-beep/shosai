import { Outlet } from "react-router";

import { PanelLayout } from "@/features/shell/ui/panel-layout";

/** Рамка пользовательской панели: сайдбар, шапка и Leo вокруг каждой страницы /app, кроме почты. */
export function Component() {
  return (
    <PanelLayout panel="dashboard">
      <Outlet />
    </PanelLayout>
  );
}
