import { Outlet } from "react-router";

import { SessionWatch } from "@/features/identity/ui/session-watch";

/** Страницы для вошедшего: если сессия кончится, человек уйдёт на вход и вернётся сюда же. */
export function SignedInLayout() {
  return (
    <>
      <SessionWatch />
      <Outlet />
    </>
  );
}
