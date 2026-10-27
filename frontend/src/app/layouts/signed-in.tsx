import { useEffect } from "react";

import { Outlet } from "react-router";

import { SessionWatch } from "@/features/identity/ui/session-watch";
import { refreshOnReturn } from "@/lib/resource-domains";

/**
 * Страницы для вошедшего: если сессия кончится, человек уйдёт на вход и вернётся сюда же; вернётся на вкладку —
 * увидит данные свежими.
 */
export function SignedInLayout() {
  useEffect(refreshOnReturn, []);
  return (
    <>
      <SessionWatch />
      <Outlet />
    </>
  );
}
