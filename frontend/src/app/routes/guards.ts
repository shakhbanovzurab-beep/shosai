import { type LoaderFunctionArgs, redirect } from "react-router";

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

/** Админ-панель /admin: только для оператора; остальным — страница «нет доступа». */
export async function operatorGuard({ request }: LoaderFunctionArgs): Promise<null> {
  const me = await signedInPerson(request);
  if (me.operator_roles.length === 0) throw redirect("/unauthorized");
  return null;
}
