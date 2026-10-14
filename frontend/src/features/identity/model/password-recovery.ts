import { requestPasswordReset, resetPassword } from "../api/password-api";
import { attempt, type Outcome } from "./outcome";

/** Попросить ссылку для нового пароля. */
export function askForResetLink(email: string, captchaToken: string | null): Promise<Outcome<void>> {
  return attempt(() => requestPasswordReset(email, captchaToken));
}

/** Сохранить новый пароль по ссылке из письма. */
export function saveNewPassword(token: string, password: string): Promise<Outcome<void>> {
  return attempt(() => resetPassword(token, password));
}
