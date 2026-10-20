import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { type MeetingOut, notesApi } from "../api/notes-api";
import { isBusyCard } from "../domain/library";
import type { MeetingPage } from "../domain/meeting-page";
import { cardOf } from "./library-cards";

/** Страница встречи из ответа сервера. */
export function pageOf(out: MeetingOut): MeetingPage {
  return {
    ...cardOf(out),
    manageable: out.manageable,
    templateId: out.template_id,
    lineCount: out.line_count,
    revision: out.revision,
    runId: out.run_id,
    participants: out.participants.map((p) => ({ id: p.id, name: p.name, email: p.email, source: p.source })),
    speakers: out.speakers.map((s) => ({ idx: s.idx, role: s.role, talkMs: s.talk_ms })),
  };
}

// По ресурсу на встречу, сделанному при первом обращении и сохранённому: возврат к встрече показывает её сразу.
const meetings = new Map<string, PollingResource<MeetingPage>>();

function meetingOf(id: string) {
  let resource = meetings.get(id);
  if (!resource) {
    // Пока встреча идёт или её записи пишутся, страница перечитывается: записи появляются сами.
    resource = createPollingResource(async () => pageOf(await notesApi.meeting(id)), isBusyCard);
    meetings.set(id, resource);
  }
  return resource;
}

export const useMeeting = (id: string) => usePollingResource(meetingOf(id));
export const refreshMeeting = (id: string) => meetingOf(id).refresh();

/** Меняет открытую страницу встречи, не дожидаясь сервера; закрытую не трогает. */
export function patchMeeting(id: string, change: (page: MeetingPage) => MeetingPage) {
  const resource = meetings.get(id);
  if (resource?.getSnapshot().status === "ready") resource.update(change);
}

/**
 * Встреча для загрузчика маршрута: ответ сервера сразу ложится в её ресурс, так что страница не просит его
 * второй раз. Ошибка API (в том числе 404) уходит загрузчику как есть.
 */
export async function loadMeeting(id: string): Promise<MeetingPage> {
  const page = pageOf(await notesApi.meeting(id));
  meetingOf(id).seed(page);
  return page;
}
