import { ApiError } from "@/lib/api/errors";

import { scheduleDeletion } from "../api/account-data-api";
import { signOut } from "./session";

/** Чем кончилась просьба удалить аккаунт. */
export type DeletionOutcome =
  | { kind: "scheduled"; eraseAt: string }
  | { kind: "reauthenticate" }
  | { kind: "mismatch" }
  | { kind: "failed"; error: unknown };

/**
 * Назначить удаление аккаунта (7 дней, вход в это время его отменяет). Сервер требует входа не раньше 15 минут
 * назад: тогда человек подтверждает себя кодом из письма и просит снова. После назначения все сессии закрыты.
 */
export async function deleteMyAccount(confirmEmail: string): Promise<DeletionOutcome> {
  try {
    const { erase_at: eraseAt } = await scheduleDeletion(confirmEmail);
    // Сервер уже закрыл сессии; выход здесь забывает токен во всех вкладках.
    await signOut().catch(() => undefined);
    return { kind: "scheduled", eraseAt };
  } catch (error) {
    if (error instanceof ApiError && error.code === "reauthentication_required") return { kind: "reauthenticate" };
    if (error instanceof ApiError && error.code === "confirmation_mismatch") return { kind: "mismatch" };
    return { kind: "failed", error };
  }
}
