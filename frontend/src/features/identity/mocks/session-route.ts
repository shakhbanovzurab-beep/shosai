// Сессия разработки (`npm run dev` без бэкенда): демо-человек вошёл сразу, вход принимает любой пароль, кроме
// «wrong», выход закрывает сессию до следующего входа — и после перезагрузки вкладки, как настоящая refresh-cookie.
// В production-сборку моки не попадают.
import { DEMO_USER } from "@/features/settings/data/demo-user";
import type { components } from "@/lib/api/generated/schema";
import { LANGUAGE_COOKIE } from "@/lib/language";

type Me = components["schemas"]["Me"];

const DEMO_TOKEN = "demo-access-token";
const REJECTED_PASSWORD = "wrong";
// Выход помнится в sessionStorage вкладки: обработчики MSW живут в странице и начинались бы заново с каждой загрузкой.
const SIGNED_OUT_KEY = "shosai-mock-signed-out";

function isSignedIn(): boolean {
  return sessionStorage.getItem(SIGNED_OUT_KEY) === null;
}

function setSignedIn(value: boolean): void {
  if (value) sessionStorage.removeItem(SIGNED_OUT_KEY);
  else sessionStorage.setItem(SIGNED_OUT_KEY, "1");
}

function interfaceLanguage(): string {
  const entry = document.cookie.split("; ").find((part) => part.startsWith(`${LANGUAGE_COOKIE}=`));
  return entry ? decodeURIComponent(entry.slice(LANGUAGE_COOKIE.length + 1)) : "en";
}

function demoMe(): Me {
  return {
    id: "00000000-0000-7000-8000-000000000001",
    email: DEMO_USER.email,
    full_name: DEMO_USER.name,
    display_name: null,
    work_role: null,
    avatar_url: null,
    language: interfaceLanguage(),
    timezone: "Europe/Amsterdam",
    country: "NL",
    home: "eu",
    consents: {
      personal_data: true,
      cross_border: true,
      marketing: false,
      improve_models: false,
      share_location: false,
    },
    operator_roles: ["owner"],
    created_at: "2026-01-01T00:00:00Z",
  };
}

const unauthorized = (code: string) => Response.json({ error: { code }, detail: code }, { status: 401 });
/** Токены демо-сессии; вход любым способом открывает её. */
export function demoSession() {
  setSignedIn(true);
  return { access_token: DEMO_TOKEN, expires_in: 1800, token_type: "bearer", csrf_token: "mock-csrf" };
}

const session = () => Response.json(demoSession());

export const loginRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { password?: string };
    if (body.password === REJECTED_PASSWORD) return unauthorized("invalid_credentials");
    setSignedIn(true);
    return session();
  },
};

export const refreshRoute = {
  POST() {
    return isSignedIn() ? session() : unauthorized("refresh_missing");
  },
};

export const logoutRoute = {
  POST() {
    setSignedIn(false);
    return Response.json({ status: "ok" });
  },
};

export const meRoute = {
  GET(request: Request) {
    return request.headers.get("authorization") === `Bearer ${DEMO_TOKEN}`
      ? Response.json(demoMe())
      : unauthorized("token_invalid");
  },
  async PATCH(request: Request) {
    const change = (await request.json()) as { language?: string };
    return Response.json({ ...demoMe(), ...(change.language ? { language: change.language } : {}) });
  },
};
