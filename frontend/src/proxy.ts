import { type NextRequest, NextResponse } from "next/server";

import { ADMIN_PANEL, PANEL_HEADER } from "@/i18n/config";

const isAdminPath = (pathname: string) => pathname === "/admin" || pathname.startsWith("/admin/");

/**
 * Marks requests for the admin panel, which is written in Russian only, so the server renders it in Russian
 * whatever language the user picked for /app. The header is rewritten on every request, so a client can't
 * set it itself. Nothing else is changed: no redirects, and the language never appears in the URL.
 */
export function proxy(request: NextRequest) {
  const headers = new Headers(request.headers);
  if (isAdminPath(request.nextUrl.pathname)) headers.set(PANEL_HEADER, ADMIN_PANEL);
  else headers.delete(PANEL_HEADER);
  return NextResponse.next({ request: { headers } });
}

/** Pages and their Server Actions only: not route handlers, build assets or files with an extension. */
export const config = {
  matcher: ["/((?!api/|_next/static|_next/image|.*\\.[a-zA-Z0-9]+$).*)"],
};
