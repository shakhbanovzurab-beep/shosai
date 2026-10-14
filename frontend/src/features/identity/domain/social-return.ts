import { type AuthProblem, authProblemOf } from "./problems";
import { isSocialProvider, type SocialProvider } from "./social-providers";

/**
 * С чем сервис вернул человека на страницу входа (адрес собирает бэкенд): билет сессии, билет согласий первого
 * входа или причина отказа.
 */
export type SocialReturn =
  | { kind: "session"; ticket: string }
  | { kind: "consent"; ticket: string; provider: SocialProvider }
  | { kind: "refused"; problem: AuthProblem }
  | { kind: "none" };

export function socialReturnOf(params: URLSearchParams): SocialReturn {
  const session = params.get("social");
  if (session) return { kind: "session", ticket: session };
  const consent = params.get("social_consent");
  const provider = params.get("social_provider") ?? "";
  if (consent && isSocialProvider(provider)) return { kind: "consent", ticket: consent, provider };
  const error = params.get("social_error");
  if (error) return { kind: "refused", problem: authProblemOf(error) };
  // Билет согласий без известного сервиса — адрес испорчен: человек просто видит вход.
  return { kind: "none" };
}

/** Адрес входа с причиной отказа сервиса — после неудачного обмена билета. */
export function socialRefusalPath(loginPath: string, problem: AuthProblem, next: string): string {
  const query = new URLSearchParams({ social_error: problem, next });
  return `${loginPath}?${query.toString()}`;
}
