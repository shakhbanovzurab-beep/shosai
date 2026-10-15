// Вход по коду, сброс пароля, вход через сервис и десктоп в `npm run dev` без бэкенда. Код из письма — 123456,
// ссылка сброса принимает любой токен, кроме «expired».
import { demoSession } from "./session-route";

const DEMO_CODE = "123456";
const RESEND_AFTER_SECONDS = 30;

const refused = (code: string, status: number, params: Record<string, number> = {}) =>
  Response.json({ error: { code, request_id: "mock-request", params }, detail: code }, { status });

// Вход по коду: адрес, начинающийся с «new», — новый человек (экран согласий), остальные входят сразу.
const NEWCOMER_PREFIX = "new";

function challengeOf(email: string): string {
  return `mock-challenge.${btoa(encodeURIComponent(email))}`;
}

function emailOf(challenge: string): string {
  return decodeURIComponent(atob(challenge.replace("mock-challenge.", "")));
}

export const emailStartRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { email?: string };
    return Response.json(
      { challenge: challengeOf(body.email ?? ""), resend_after_seconds: RESEND_AFTER_SECONDS },
      { status: 202 },
    );
  },
};

export const emailVerifyRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { challenge?: string; code?: string };
    if (body.code !== DEMO_CODE) return refused("invalid_code", 400);
    if (emailOf(body.challenge ?? "").startsWith(NEWCOMER_PREFIX)) {
      return Response.json({ session: null, consent_ticket: "mock-consent-ticket", next: "/app" });
    }
    return Response.json({ session: { ...demoSession(), next: "/app" }, consent_ticket: null, next: "/app" });
  },
};

export const emailResendRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { challenge?: string };
    return Response.json({ challenge: body.challenge, resend_after_seconds: RESEND_AFTER_SECONDS }, { status: 202 });
  },
};

export const resetRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { token?: string };
    return body.token === "expired" ? refused("invalid_token", 400) : new Response(null, { status: 204 });
  },
};

// Как на сервере: русский интерфейс видит Яндекс и VK, остальной мир — Google и GitHub (406-ФЗ).
export const socialProvidersRoute = {
  GET(request: Request) {
    const russian = new URL(request.url).searchParams.get("language") === "ru";
    const providers = russian ? ["yandex", "vk"] : ["google", "github"];
    return Response.json({ providers, yandex_client_id: null, google_client_id: null });
  },
};

export const socialSessionRoute = {
  POST() {
    return Response.json({ ...demoSession(), next: "/app" });
  },
};

export const desktopCodeRoute = {
  POST() {
    return Response.json({ code: "mock-desktop-code", expires_in: 60 });
  },
};
