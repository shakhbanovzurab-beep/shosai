import {
  type RegistrationForm,
  type RegistrationStarted,
  resendRegistrationCode,
  startRegistration,
  verifyRegistration,
} from "../api/registration-api";
import { attempt, type Outcome } from "./outcome";
import { signedIn } from "./session";

/** Начать регистрацию; при успехе — номер заявки и пауза до повторной отправки кода. */
export function register(form: RegistrationForm): Promise<Outcome<RegistrationStarted>> {
  return attempt(() => startRegistration(form));
}

/** Подтвердить почту кодом: аккаунт заведён, человек вошёл. */
export function confirmRegistration(registrationId: string, code: string): Promise<Outcome<void>> {
  return attempt(async () => {
    const account = await verifyRegistration(registrationId, code);
    await signedIn(account.access_token);
  });
}

export function resendCode(registrationId: string): Promise<Outcome<RegistrationStarted>> {
  return attempt(() => resendRegistrationCode(registrationId));
}
