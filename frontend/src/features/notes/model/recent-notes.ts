import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { notesApi } from "../api/notes-api";
import { isBusyCard } from "../domain/library";
import { cardOf } from "./library-cards";

// Главной нужны четыре последние встречи: страница сервера ровно такого размера, а не первая страница библиотеки.
const RECENT = 4;

const recentResource = createPollingResource(
  async () => (await notesApi.page({ limit: RECENT })).items.map(cardOf),
  (cards) => cards.some(isBusyCard),
);

/** Последние встречи человека для главной; обновляются сами, пока какая-то из них пишется. */
export const useRecentNotes = () => usePollingResource(recentResource);

/**
 * Последние записи страницей библиотеки — для раздела «Встречи» (слайс meetings, ADR 0057): идущие, недавние и
 * прошедшие встречи там — записи «Заметок». Раздел опрашивает их сам, пока какая-то идёт или пишется.
 */
export const recentRecordings = async (limit: number) => (await notesApi.page({ limit })).items.map(cardOf);
