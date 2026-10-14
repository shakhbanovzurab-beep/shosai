import { type LoaderFunctionArgs, redirect } from "react-router";

import { LOGIN_PATH, safeNext } from "@/features/identity/domain/next-path";
import { type SocialReturn, socialRefusalPath, socialReturnOf } from "@/features/identity/domain/social-return";
import { startSession } from "@/features/identity/model/session";
import { finishSocialSignIn } from "@/features/identity/model/social-sign-in";

export type LoginEntry = Exclude<SocialReturn, { kind: "session" }>;

/**
 * Вход: билет сессии от сервиса обменивается здесь же, ровно один раз, и адрес сразу меняется — повторная
 * загрузка страницы со старым билетом дала бы отказ на пустом месте. Уже вошедший человек возвращается туда,
 * куда шёл; экран согласий первого входа показывается и ему — это заводится новый аккаунт.
 */
export async function loader({ request }: LoaderFunctionArgs): Promise<LoginEntry> {
  const params = new URL(request.url).searchParams;
  const next = safeNext(params.get("next"));
  const entry = socialReturnOf(params);
  if (entry.kind === "session") {
    const outcome = await finishSocialSignIn(entry.ticket);
    throw redirect(outcome.kind === "done" ? outcome.value : socialRefusalPath(LOGIN_PATH, outcome.problem, next));
  }
  if (entry.kind === "consent") return entry;
  const me = await startSession();
  if (me !== null) throw redirect(next);
  return entry;
}
