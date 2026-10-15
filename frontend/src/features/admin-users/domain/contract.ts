import type { components } from "@/lib/api/generated/schema";

/** Что сервер отдаёт администратору об аккаунтах (`/v1/admin/users*`). */
export type AdminUser = components["schemas"]["AdminUser"];
export type AdminUserCard = components["schemas"]["AdminUserCard"];
export type AccountState = components["schemas"]["AccountState"];
export type UsersPage = components["schemas"]["Page_AdminUser_"];

/** Действия администратора над аккаунтом (ADR 0049): бана нет. */
export type AccountAction = "block" | "unblock";
