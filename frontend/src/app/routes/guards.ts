import { data, type LoaderFunctionArgs, redirect } from "react-router";

import { ADMIN_HOME } from "@/features/admin-sign-in/domain/login-path";
import { adminSignedIn } from "@/features/admin-sign-in/model/admin-guard";
import { loginPathFor } from "@/features/identity/domain/next-path";
import type { Me } from "@/features/identity/domain/session";
import { startSession } from "@/features/identity/model/session";
import { readClientCookie, setClientCookie } from "@/lib/cookie.client";
import { isLanguageCode, LANGUAGE_COOKIE } from "@/lib/language";

const YEAR_DAYS = 365;
// Язык аккаунта перенимается один раз за загрузку вкладки: дальше его ведёт выбор в меню.
let languageAdopted = false;

function pageOf(request: Request): string {
  const url = new URL(request.url);
  return `${url.pathname}${url.search}`;
}

async function signedInPerson(request: Request): Promise<Me> {
  const me = await startSession();
  if (me === null) throw redirect(loginPathFor(pageOf(request)));
  return me;
}

/**
 * Панель /app: только для вошедшего; сессия запущена ещё в main.tsx, так что loader ждёт уже идущее
 * обновление, параллельно с каталогом языка и кодом страницы. На новом устройстве язык берётся из аккаунта.
 */
export async function signedInGuard({ request }: LoaderFunctionArgs): Promise<null> {
  const me = await signedInPerson(request);
  if (!languageAdopted) {
    languageAdopted = true;
    if (isLanguageCode(me.language) && readClientCookie(LANGUAGE_COOKIE) !== me.language) {
      setClientCookie(LANGUAGE_COOKIE, me.language, YEAR_DAYS);
      throw redirect(pageOf(request));
    }
  }
  return null;
}

/**
 * Админ-панель /admin: только для вошедшего администратора (ADR 0049). Остальным — «не найдено», а не переход
 * на вход: адрес страницы входа отдельный и нигде не показан.
 */
export async function adminGuard(): Promise<null> {
  if (!(await adminSignedIn())) throw data(null, { status: 404 });
  return null;
}

/** Страница входа в админку: вошедшего администратора сразу ведёт в админку. */
export async function adminSignInGuard(): Promise<null> {
  if (await adminSignedIn()) throw redirect(ADMIN_HOME);
  return null;
}
