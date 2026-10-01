// Сессия персоны при записи: вход напрямую в API черновика, затем куки и
// localStorage браузера — как у пользователя, который уже входил раньше.
//
// Загрузка страницы после этого идёт по-настоящему: фронтенд черновика видит
// сохранённого пользователя без токена, зовёт /v1/auth/refresh с кукой и CSRF —
// и эти обмены попадают в фикстуру, как у живого пользователя.

import { request, type APIRequestContext, type BrowserContext } from "@playwright/test";

import { DRAFT_API } from "./capture.ts";

/** Общий пароль персон стенда (recording/seed/personas.py). */
const PERSONA_PASSWORD = "parity-password-1";
const PERSONA_DOMAIN = "parity.test";

export interface PersonaSession {
  readonly csrfToken: string;
  /** Профиль из /v1/auth/me — тот, что фронтенд хранит в wh-auth. */
  readonly user: Record<string, unknown>;
}

interface LoginResponse {
  readonly access_token: string;
  readonly csrf_token?: string;
}

interface ParsedCookie {
  readonly name: string;
  readonly value: string;
  readonly path: string;
  readonly httpOnly: boolean;
}

function parseSetCookie(setCookie: string): ParsedCookie {
  const [pair = "", ...attributes] = setCookie.split(";").map((part) => part.trim());
  const separator = pair.indexOf("=");
  const lowered = attributes.map((attribute) => attribute.toLowerCase());
  const pathAttribute = lowered.find((attribute) => attribute.startsWith("path="));
  return {
    name: pair.slice(0, separator),
    value: pair.slice(separator + 1),
    path: pathAttribute === undefined ? "/" : pathAttribute.slice("path=".length),
    // CSRF-кука черновика читается из JS, refresh-кука — нет.
    httpOnly: lowered.includes("httponly"),
  };
}

const COMMIT_DEADLINE_MS = 5000;

/**
 * Профиль после входа — когда вход уже закоммичен.
 *
 * Черновик коммитит транзакцию в зависимости `get_db` после того, как ответ на
 * вход сформирован. Профиль, запрошенный сразу, иногда видит базу до коммита —
 * без времени входа, — и запись переставала повторяться. Ждём, пока время
 * входа появится.
 */
async function committedProfile(
  api: APIRequestContext,
  persona: string,
  accessToken: string,
): Promise<Record<string, unknown>> {
  const deadline = Date.now() + COMMIT_DEADLINE_MS;
  for (;;) {
    const me = await api.get("/v1/auth/me", { headers: { authorization: `Bearer ${accessToken}` } });
    if (!me.ok()) throw new Error(`Профиль персоны ${persona}: HTTP ${me.status()}`);
    const user = (await me.json()) as Record<string, unknown>;
    if (user["last_login_at"] !== null) return user;
    if (Date.now() > deadline) throw new Error(`Вход персоны ${persona} не закоммичен за ${COMMIT_DEADLINE_MS} мс`);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

/** Входит персоной и переносит её куки в контекст браузера. */
export async function signIn(context: BrowserContext, persona: string): Promise<PersonaSession> {
  const api = await request.newContext({ baseURL: DRAFT_API });
  try {
    const login = await api.post("/v1/auth/login", {
      data: { email: `${persona}@${PERSONA_DOMAIN}`, password: PERSONA_PASSWORD },
    });
    if (!login.ok()) {
      throw new Error(`Вход персоны ${persona}: HTTP ${login.status()} ${await login.text()}`);
    }
    const tokens = (await login.json()) as LoginResponse;
    const setCookies = login
      .headersArray()
      .filter((header) => header.name.toLowerCase() === "set-cookie")
      .map((header) => parseSetCookie(header.value));
    await context.addCookies(setCookies.map((cookie) => ({ ...cookie, domain: "parity.test", sameSite: "Lax" as const })));
    const user = await committedProfile(api, persona, tokens.access_token);
    const csrfCookie = setCookies.find((cookie) => cookie.name === "meetassist_csrf");
    return { csrfToken: tokens.csrf_token ?? csrfCookie?.value ?? "", user };
  } finally {
    await api.dispose();
  }
}
