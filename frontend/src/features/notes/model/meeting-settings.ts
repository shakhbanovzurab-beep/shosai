"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { meetingSettingsApi } from "../api/meeting-settings-api";

/*
 * «Не сохранять мои встречи» (MT-D6): с ним встречи, начатые дальше, видны вживую, но не хранятся — ни
 * расшифровки, ни заметок Leo, ни записи, ни ссылки, ни памяти Leo; минуты считаются; загрузка записей закрыта.
 * Уже сохранённые встречи остаются. Переключатель стоит в Settings › Privacy.
 */

export const keepingResource = createPollingResource(meetingSettingsApi.keepsMeetings);

/** Хранит ли Shosai встречи человека. */
export const useKeepsMeetings = () => usePollingResource(keepingResource);
export const retryKeepsMeetings = () => keepingResource.refresh();

/** Сохраняет выбор: переключатель двигается сразу и возвращается, если сервер отказал; ошибка — вызывающему. */
export async function keepMeetings(keep: boolean): Promise<void> {
  const before = keepingResource.getSnapshot();
  keepingResource.update(() => keep);
  try {
    const saved = await meetingSettingsApi.keepMeetings(keep);
    keepingResource.update(() => saved);
  } catch (error) {
    if (before.status === "ready") keepingResource.update(() => before.data);
    throw error;
  }
}
