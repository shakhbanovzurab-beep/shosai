// Сессия разработки (`npm run dev` без бэкенда): демо-человек вошёл сразу, вход принимает любой пароль, кроме
// «wrong», выход закрывает сессию до следующего входа — и после перезагрузки вкладки, как настоящая refresh-cookie.
// В production-сборку моки не попадают.
import { applyPatch, demoMe } from "./demo-person";

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
    return Response.json(applyPatch((await request.json()) as Parameters<typeof applyPatch>[0]));
  },
};

// Админка в `npm run dev`: администратор вошёл, пока не вышел (ADR 0049); любой логин и пароль подходят.
let adminSignedIn = true;
const noContent = () => new Response(null, { status: 204 });

export const adminSessionRoute = {
  GET() {
    return adminSignedIn
      ? noContent()
      : Response.json({ error: { code: "admin_sign_in_required", request_id: "mock-request" } }, { status: 401 });
  },
  POST() {
    adminSignedIn = true;
    return noContent();
  },
  DELETE() {
    adminSignedIn = false;
    return noContent();
  },
};
