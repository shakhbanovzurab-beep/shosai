import { type Credentials, signInWithPassword } from "../api/session-api";
import { attempt, type Outcome } from "./outcome";
import { signedIn } from "./session";

/** Войти паролем; неудача — причина, которую форма превращает в слова. */
export function signIn(credentials: Credentials): Promise<Outcome<void>> {
  return attempt(async () => {
    const tokens = await signInWithPassword(credentials);
    await signedIn(tokens.access_token);
  });
}
