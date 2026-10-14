import { completeSocialSignIn, registerWithSocial, type SocialRegistration } from "../api/social-api";
import { safeNext } from "../domain/next-path";
import { attempt, type Outcome } from "./outcome";
import { signedIn } from "./session";

/** Билет из адреса после сервиса — сессия; результат — страница кабинета, куда человек шёл. */
export function finishSocialSignIn(ticket: string): Promise<Outcome<string>> {
  return attempt(async () => {
    const session = await completeSocialSignIn(ticket);
    await signedIn(session.access_token);
    return safeNext(session.next);
  });
}

/** Первый вход через сервис: аккаунт с согласиями, сессия и страница, куда человек шёл. */
export function registerThroughSocial(registration: SocialRegistration): Promise<Outcome<string>> {
  return attempt(async () => {
    const session = await registerWithSocial(registration);
    await signedIn(session.access_token);
    return safeNext(session.next);
  });
}
