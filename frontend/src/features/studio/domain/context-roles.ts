import type { ContextRoles, StudioRole } from "./contract";
import { ROLES } from "./roles";

/** Тумблер блока «Как это отправляется»: «Все» или одна роль. */
export type ContextRoleOption = "all" | StudioRole;

/** Включён ли тумблер: при «Все» отдельные роли выключены. */
export function isSwitchedOn(roles: ContextRoles, option: ContextRoleOption): boolean {
  if (option === "all") return roles === "all";
  return roles !== "all" && roles.includes(option);
}

/**
 * Выбор после переключения тумблера. «Все» включается одно и выключает отдельные роли; включённая роль
 * выключает «Все» и добавляется к уже выбранным. Роли идут в порядке Studio.
 */
export function switched(roles: ContextRoles, option: ContextRoleOption, on: boolean): ContextRoles {
  if (option === "all") return on ? "all" : [];
  const next = new Set(roles === "all" ? [] : roles);
  if (on) next.add(option);
  else next.delete(option);
  return ROLES.map((role) => role.id).filter((id) => next.has(id));
}
