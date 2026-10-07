import { NextResponse } from "next/server";

import { getTranslations } from "next-intl/server";

import { ADMIN_LANGUAGE } from "@/i18n/config";
import { resolveLocale } from "@/i18n/resolve-locale";
import { LANGUAGE_COOKIE, type LanguageCode } from "@/lib/language";

/**
 * The interface language a request is answered in: Russian for the admin panel's API, otherwise the user's
 * choice (the cookie). The backend gets it as `Accept-Language`, to word errors and new data in it.
 */
export function requestLanguage(request: Request): LanguageCode {
  if (new URL(request.url).pathname.startsWith("/api/admin/")) return ADMIN_LANGUAGE;
  const cookie = request.headers
    .get("cookie")
    ?.split("; ")
    .find((entry) => entry.startsWith(`${LANGUAGE_COOKIE}=`))
    ?.slice(LANGUAGE_COOKIE.length + 1);
  return resolveLocale(null, cookie);
}

/**
 * Forwards an API request to the FastAPI backend when `BACKEND_API_URL` is set, e.g.
 * `http://api:8000`, keeping method, content type and body. `path` is the backend path, such as
 * `/v1/knowledge-base/documents`. Returns `null` when no backend is configured, so the route
 * handler can answer from its in-memory demo instead.
 */
export async function forwardToBackend(request: Request, path: string): Promise<Response | null> {
  const base = process.env.BACKEND_API_URL;
  if (!base) return null;

  const language = requestLanguage(request);
  const headers = new Headers({ "accept-language": language });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const key = process.env.BACKEND_API_KEY;
  if (key) headers.set("authorization", `Bearer ${key}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  try {
    const upstream = await fetch(`${base.replace(/\/$/, "")}${path}`, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // Streams uploads through instead of buffering them.
      ...(hasBody ? { duplex: "half" } : {}),
      cache: "no-store",
    } as RequestInit);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    const t = await getTranslations({ locale: language, namespace: "common" });
    return NextResponse.json({ detail: t("errors.backendUnreachable") }, { status: 502 });
  }
}

/**
 * Reads from the FastAPI backend during server rendering, e.g. `/v1/apps/latest?platform=macos`.
 * Returns `null` when no backend is configured, so the caller can use its in-memory demo instead;
 * a network failure rejects.
 */
export function fetchFromBackend(path: string): Promise<Response> | null {
  const base = process.env.BACKEND_API_URL;
  if (!base) return null;
  const key = process.env.BACKEND_API_KEY;
  return fetch(`${base.replace(/\/$/, "")}${path}`, {
    headers: key ? { authorization: `Bearer ${key}` } : undefined,
    cache: "no-store",
  });
}

/** An error in FastAPI's shape, `{ "detail": message }`. */
export const detail = (message: string, status: number) => NextResponse.json({ detail: message }, { status });
