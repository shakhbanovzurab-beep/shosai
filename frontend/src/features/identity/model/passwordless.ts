import { type EmailStartForm, resendEmailCode, startEmailSignIn, verifyEmailCode } from "../api/email-sign-in-api";
import { exchangeWidgetToken } from "../api/social-api";
import { safeNext } from "../domain/next-path";
import { attempt, type Outcome } from "./outcome";
import { signedIn } from "./session";
import { finishSocialSignIn } from "./social-sign-in";

/** Чем кончается вход без пароля: человек вошёл — куда ему дальше; новый человек — билет экрана согласий. */
export type Arrival = { kind: "signed-in"; next: string } | { kind: "consent"; ticket: string };

export interface CodeSent {
  challenge: string;
  resendAfterSeconds: number;
}

/** Прислать код на почту (ADR 0048). */
export function sendCode(form: EmailStartForm): Promise<Outcome<CodeSent>> {
  return attempt(async () => {
    const started = await startEmailSignIn(form);
    return { challenge: started.challenge, resendAfterSeconds: started.resend_after_seconds };
  });
}

/** Новый код по тому же вызову: через сколько секунд можно попросить ещё. */
export function resendCode(challenge: string): Promise<Outcome<CodeSent>> {
  return attempt(async () => {
    const started = await resendEmailCode(challenge);
    return { challenge: started.challenge, resendAfterSeconds: started.resend_after_seconds };
  });
}

/** Код из письма: известный человек входит, новый получает экран согласий. */
export function confirmCode(challenge: string, code: string): Promise<Outcome<Arrival>> {
  return attempt(async (): Promise<Arrival> => {
    const verified = await verifyEmailCode(challenge, code);
    if (verified.session) {
      await signedIn(verified.session.access_token);
      return { kind: "signed-in", next: safeNext(verified.next) };
    }
    if (verified.consent_ticket) return { kind: "consent", ticket: verified.consent_ticket };
    throw new Error("email verification answered neither a session nor a consent ticket");
  });
}

const UNANSWERED: Outcome<Arrival> = { kind: "refused", problem: "unknown", requestId: null, retryAfterSeconds: null };

/** Токен фирменного виджета Яндекса или Google: сервер сверяет его у провайдера и отдаёт билет. */
export async function arriveByWidget(
  provider: "yandex" | "google",
  token: string,
  next: string,
  language: string,
): Promise<Outcome<Arrival>> {
  const exchanged = await attempt(() => exchangeWidgetToken(provider, token, next, language));
  if (exchanged.kind === "refused") return exchanged;
  const { social, social_consent: consent } = exchanged.value;
  if (consent) return { kind: "done", value: { kind: "consent", ticket: consent } };
  if (!social) return UNANSWERED;
  const finished = await finishSocialSignIn(social);
  return finished.kind === "done" ? { kind: "done", value: { kind: "signed-in", next: finished.value } } : finished;
}
