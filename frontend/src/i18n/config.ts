import type { LanguageCode } from "@/lib/language";

/** Админ-панель написана только по-русски, какой бы язык пользователь ни выбрал для /app. */
export const ADMIN_LANGUAGE: LanguageCode = "ru";

/** Принадлежит ли путь админ-панели. */
export const isAdminPath = (pathname: string) => pathname === "/admin" || pathname.startsWith("/admin/");

/**
 * Часовой пояс форматирования всех дат. Демо-данные и доменные форматтеры — в UTC; компонент, показывающий
 * местное время зрителя (часы в шапке), форматирует его сам. См. docs/i18n.md.
 */
export const TIME_ZONE = "UTC";
