"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";

import { workspacesApi } from "../api/workspaces-api";
import type { AdminWorkspaceDetail } from "../domain/contract";
import { workspaceResource, workspacesResource } from "./resources";

/* What the platform's team does to a workspace. Each one updates the open page and the list. */

function applied(detail: AdminWorkspaceDetail) {
  workspaceResource(detail.id).update(() => detail);
  void workspacesResource.refresh();
}

/** Resolves to null on success, or the message for the dialog. */
async function run(change: () => Promise<AdminWorkspaceDetail>, success: string, description?: string) {
  try {
    applied(await change());
    toast.success(success, { description });
    return null;
  } catch (error) {
    return errorMessage(error) ?? "Не удалось выполнить действие.";
  }
}

export const changeSeats = (id: string, seats: number) =>
  run(() => workspacesApi.setSeats(id, seats), "Количество мест изменено", "Новая сумма — со следующего списания.");

export const suspend = (id: string, reason: string) =>
  run(
    () => workspacesApi.suspend(id, reason),
    "Доступ приостановлен",
    "Участники видят, что пространство приостановлено. Данные не удалены.",
  );

export async function resume(id: string) {
  const failure = await run(() => workspacesApi.resume(id), "Доступ восстановлен");
  if (failure) toast.error("Не удалось восстановить доступ", { description: failure });
}

export const transferOwner = (id: string, memberId: string, name: string) =>
  run(
    () => workspacesApi.transferOwner(id, memberId),
    `Владелец теперь — ${name}`,
    "Прежний владелец стал администратором.",
  );

/** Deletes it for good; true when it's gone, so the page can go back to the list. */
export async function removeWorkspace(id: string, name: string) {
  try {
    await workspacesApi.remove(id);
    workspacesResource.update((data) => ({ workspaces: data.workspaces.filter((w) => w.id !== id) }));
    toast.success(`Пространство «${name}» удалено`, {
      description: "Записи и файлы участников остались у их владельцев.",
    });
    return true;
  } catch (error) {
    toast.error("Не удалось удалить пространство", { description: apiErrorDescription(error) });
    return false;
  }
}
