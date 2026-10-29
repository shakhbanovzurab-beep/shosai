import { toast } from "sonner";

import { studioApi } from "../api/studio-api";
import type { ContextRoles, RoleModelSettings } from "../domain/contract";
import { describeStudioError, type ProblemWords } from "./studio-problem-words";
import { contextResource, modelsResource } from "./studio-resources";

/** Автосохранение контекста: отклоняется при сбое, чтобы редактор предложил повтор. */
export async function saveContext(content: string) {
  const saved = await studioApi.saveContext(content);
  contextResource.update(() => saved);
}

/** Куда подмешивать контекст — сразу на экране; если сервер отказал, выбор возвращается. */
export async function saveContextRoles(next: ContextRoles, previous: ContextRoles, words: ProblemWords) {
  const set = (roles: ContextRoles) => contextResource.update((data) => ({ ...data, roles }));
  set(next);
  try {
    set((await studioApi.saveContextRoles(next)).roles);
  } catch (error) {
    set(previous);
    toast.error(words.studio("preview.saveFailed"), { description: describeStudioError(error, words) });
  }
}

/** Сохраняет настройки роли сразу: изменение видно мгновенно и откатывается, если сервер отказал. */
export async function saveRoleSettings(next: RoleModelSettings, previous: RoleModelSettings, words: ProblemWords) {
  const swap = (value: RoleModelSettings) =>
    modelsResource.update((data) => ({ ...data, roles: data.roles.map((r) => (r.role === value.role ? value : r)) }));
  swap(next);
  try {
    const { role, ...body } = next;
    swap(await studioApi.updateRole(role, body));
  } catch (error) {
    swap(previous);
    toast.error(words.studio("models.saveFailed"), { description: describeStudioError(error, words) });
  }
}
