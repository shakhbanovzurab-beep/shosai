/**
 * Причины, по которым вход, регистрация, сброс пароля или вход через сервис не удались, — коды ответа бэкенда
 * (identity, ADR 0008). Интерфейс превращает их в слова; неизвестный код — общая ошибка с номером запроса.
 */
export const AUTH_PROBLEMS = [
  "invalid_credentials",
  "captcha_failed",
  "email_not_verified",
  "account_banned",
  "account_frozen",
  "account_disabled",
  "account_unavailable",
  "rate_limited",
  "invalid_email",
  "invalid_country",
  "email_registered",
  "email_domain_not_allowed",
  "password_too_short",
  "password_too_long",
  "personal_data_consent_required",
  "cross_border_consent_required",
  "invalid_code",
  "code_locked",
  "too_many_codes",
  "sign_in_unavailable",
  "registration_locked",
  "registration_unavailable",
  "resend_too_soon",
  "too_many_resends",
  "invalid_token",
  "social_login_cancelled",
  "social_email_required",
  "social_provider_disabled",
  "social_provider_failed",
  "social_state_invalid",
  "social_link_requires_sign_in",
  "social_unavailable",
] as const;

export type AuthProblem = (typeof AUTH_PROBLEMS)[number] | "unknown";

export function authProblemOf(code: string | null | undefined): AuthProblem {
  return AUTH_PROBLEMS.find((problem) => problem === code) ?? "unknown";
}
