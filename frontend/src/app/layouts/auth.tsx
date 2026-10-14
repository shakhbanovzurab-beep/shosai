import { Outlet } from "react-router";

import { AuthScreen } from "@/features/identity/ui/auth-screen";

/** Каркас страниц входа: афиша остаётся на месте, пока человек переходит между входом, регистрацией и сбросом. */
export function Component() {
  return (
    <AuthScreen>
      <Outlet />
    </AuthScreen>
  );
}
