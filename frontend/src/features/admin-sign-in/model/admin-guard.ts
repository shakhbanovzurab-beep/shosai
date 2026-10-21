import { readAdminSession } from "../api/admin-session-api";
import { setBusinessZone } from "./business-zone";

/*
 * Проверка сессии для стражей маршрутов: отдельный лёгкий модуль, чтобы начальный бандл не тянул меню и выход
 * админки (react-query, тосты).
 */

/** Вошёл ли администратор; заодно запоминает деловой пояс платформы, в котором админка показывает даты. */
export async function adminSignedIn(): Promise<boolean> {
  const session = await readAdminSession();
  if (session) setBusinessZone(session.business_time_zone);
  return session !== null;
}
