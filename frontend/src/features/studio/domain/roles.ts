import type { ModelCapability, StudioRole } from "./contract";

/**
 * Роль, которую играет ассистент. Её название, описание и подсказка «?» (где роль проявляется и чем управляет
 * её промт) — слова каталога `studio` по id роли (`roles.<id>.name|description|help`). Расшифровка речи — выбор
 * платформы, а не роль Studio (ST-D2).
 */
export type RoleDefinition = {
  id: StudioRole;
  /** Что должна уметь модель роли. */
  requires: ModelCapability;
};

export const ROLES: RoleDefinition[] = [
  { id: "live_answers", requires: "text" },
  { id: "screenshots", requires: "vision" },
  { id: "code", requires: "text" },
  { id: "system_design", requires: "text" },
  { id: "notes", requires: "text" },
];
