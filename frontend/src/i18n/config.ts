import type { LanguageCode } from "@/lib/language";

/** Админ-панель написана только по-русски, какой бы язык пользователь ни выбрал для /app. */
export const ADMIN_LANGUAGE: LanguageCode = "ru";

/** Принадлежит ли путь админ-панели. */
export const isAdminPath = (pathname: string) => pathname === "/admin" || pathname.startsWith("/admin/");
