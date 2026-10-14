// Регистрация, сброс пароля, вход через сервис и десктоп в `npm run dev` без бэкенда. Код из письма — 123456,
// ссылка сброса принимает любой токен, кроме «expired»; сервисы входа видны все четыре.
import { demoSession } from "./session-route";

const DEMO_CODE = "123456";
const RESEND_AFTER_SECONDS = 30;

const refused = (code: string, status: number, params: Record<string, number> = {}) =>
  Response.json({ error: { code, request_id: "mock-request", params }, detail: code }, { status });

export const registerRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { email?: string; consents?: { personal_data?: boolean } };
    if (body.email?.startsWith("taken@")) return refused("email_registered", 409);
    if (body.consents?.personal_data !== true) return refused("personal_data_consent_required", 422);
    return Response.json(
      { registration_id: crypto.randomUUID(), resend_after_seconds: RESEND_AFTER_SECONDS },
      { status: 202 },
    );
  },
};

export const verifyRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { code?: string };
    if (body.code !== DEMO_CODE) return refused("invalid_code", 400);
    return Response.json({ user_id: "00000000-0000-7000-8000-000000000001", ...demoSession() }, { status: 201 });
  },
};

export const resendRoute = {
  POST() {
    return Response.json(
      { registration_id: crypto.randomUUID(), resend_after_seconds: RESEND_AFTER_SECONDS },
      { status: 202 },
    );
  },
};

export const forgotRoute = {
  POST() {
    return new Response(null, { status: 202 });
  },
};

export const resetRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { token?: string };
    return body.token === "expired" ? refused("invalid_token", 400) : new Response(null, { status: 204 });
  },
};

export const socialProvidersRoute = {
  GET() {
    return Response.json({
      providers: ["yandex", "vk", "google", "github"],
      yandex_client_id: null,
      google_client_id: null,
    });
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
