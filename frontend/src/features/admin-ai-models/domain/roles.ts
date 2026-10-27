import type { AiModel, ModelRole, RoleDefault } from "./contract";

/** Роли с моделью по умолчанию: Leo и пять ролей Studio; картинки читают модели Leo и скриншотов. */
export const ROLES: readonly { id: ModelRole; label: string; vision: boolean }[] = [
  { id: "leo", label: "Leo", vision: true },
  { id: "live_answers", label: "Ответы на встрече", vision: false },
  { id: "screenshots", label: "Скриншоты", vision: true },
  { id: "code", label: "Код", vision: false },
  { id: "system_design", label: "System Design", vision: false },
  { id: "notes", label: "Заметки и карты", vision: false },
];

/** Модели, которые могут быть умолчанием роли: включённые, стандартные, умеющие нужное роли. */
export function candidatesFor(models: AiModel[], vision: boolean): AiModel[] {
  return models.filter(
    (model) =>
      model.enabled &&
      model.tier === "standard" &&
      model.capabilities.includes("text") &&
      (!vision || model.capabilities.includes("vision")),
  );
}

/** Держит ли модель умолчание или запасная модель какой-нибудь роли. */
export function heldByDefaults(defaults: RoleDefault[], modelId: string): boolean {
  return defaults.some((item) => item.model_id === modelId || item.fallback_model_id === modelId);
}

/** Умолчание роли, если оно задано. */
export function defaultOf(defaults: RoleDefault[], role: ModelRole): RoleDefault | undefined {
  return defaults.find((item) => item.role === role);
}
