import { resetPassword } from "../api/password-api";
import { attempt, type Outcome } from "./outcome";

/** Сохранить новый пароль по ссылке из письма. */
export function saveNewPassword(token: string, password: string): Promise<Outcome<void>> {
  return attempt(() => resetPassword(token, password));
}
