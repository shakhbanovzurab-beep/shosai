import { Outlet } from "react-router";

import { PanelLayout } from "@/features/shell/ui/panel-layout";

/** Рамка админ-панели вокруг каждой страницы /admin. */
export function Component() {
  return (
    <PanelLayout panel="admin">
      <Outlet />
    </PanelLayout>
  );
}
