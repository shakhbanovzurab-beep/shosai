"use client";

import { addMinutes } from "date-fns";

import { isServed, MOCK_API } from "@/config/unserved-slices";
import { isBusyCard, type MeetingCard } from "@/features/notes/domain/library";
import { recentRecordings } from "@/features/notes/model/recent-notes";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import type { Meeting } from "../domain/meeting";

/**
 * Отвечает ли API слайса meetings: без него запланированные встречи (образцы meetings и calendar), фильтр
 * «Предстоящие» и «Новая встреча» не показываются — раздел состоит из записей «Заметок».
 */
export const MEETINGS_SERVED = isServed("meetings");
// Записи — страница библиотеки «Заметок»: идущие, «Недавние» и «Прошедшие» раздела.
const RECORDINGS = 50;

/** Запись «Заметок» как встреча: идёт, пока её не закончили; итог Leo — когда заметки готовы. */
export function meetingOfRecording(card: MeetingCard): Meeting {
  return {
    id: `note-${card.id}`,
    title: card.title,
    start: card.startedAt,
    end: addMinutes(new Date(card.startedAt), card.durationMinutes).toISOString(),
    source: card.source === "import" ? "upload" : "recording",
    joinUrl: null,
    location: null,
    participants: card.participantNames.map((name) => ({ name })),
    recap:
      card.notes === "ready" && card.summary
        ? { noteId: card.id, summary: card.summary, tasks: card.actionItems, decisions: null }
        : null,
    recording: { noteId: card.id, live: card.status === "active", busy: isBusyCard(card) },
  };
}

// У «Заметок» есть API и нет моков (F2-D1): на моках раздел показывает их образцы, как до API.
async function recordings(): Promise<Meeting[]> {
  if (MOCK_API) return (await import("./sample-recordings")).sampleRecordings();
  return (await recentRecordings(RECORDINGS)).map(meetingOfRecording);
}

async function scheduled(): Promise<Meeting[]> {
  return MEETINGS_SERVED ? (await import("../data/demo-meetings")).demoMeetings() : [];
}

/**
 * Встречи раздела: записи «Заметок» и, пока у meetings нет API, их образцы. Опрашивается, пока запись идёт или
 * её заметки пишутся, — так идущая встреча сама переходит в прошедшие с итогом Leo.
 */
export const meetingsResource = createPollingResource(
  async () => {
    const [plans, recorded] = await Promise.all([scheduled(), recordings()]);
    return [...plans, ...recorded];
  },
  (meetings) => meetings.some((meeting) => meeting.recording?.busy === true),
);

export const useMeetings = () => usePollingResource(meetingsResource);
