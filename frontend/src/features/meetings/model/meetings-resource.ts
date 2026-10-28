"use client";

import { addMinutes } from "date-fns";

import { isServed, MOCK_API } from "@/config/unserved-slices";
import { isBusyCard, type MeetingCard } from "@/features/notes/domain/library";
import { recentRecordings } from "@/features/notes/model/recent-notes";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { type OwnedRoom, roomApi } from "../api/room-api";
import type { Meeting } from "../domain/meeting";
import { roomPathOf } from "./start-meeting";

/** Свои комнаты Shosai отвечают (meetings A10): «Новая встреча» и идущие звонки. */
export const ROOMS_SERVED = isServed("meetings");
/**
 * Расписание — у «Календаря»: пока у него нет API, запланированных встреч, фильтра «Предстоящие» и плана дня нет —
 * раздел состоит из идущих звонков и записей «Заметок».
 */
export const SCHEDULE_SERVED = isServed("calendar");
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
  return SCHEDULE_SERVED ? (await import("../data/demo-meetings")).demoMeetings() : [];
}

/** Идущий звонок своей комнаты как встреча раздела: вход — её страница в кабинете. */
export function meetingOfRoom(room: OwnedRoom): Meeting {
  const start = room.call?.started_at ?? room.created_at;
  return {
    id: `room-${room.id}`,
    title: room.title ?? "",
    start,
    end: start,
    source: "shosai",
    joinUrl: roomPathOf(room.link),
    location: null,
    participants: [],
    recap: null,
    recording: null,
    endless: true,
  };
}

// На моках идущая комната — среди образцов расписания; на API — свои комнаты со звонком.
async function liveRooms(): Promise<Meeting[]> {
  return ROOMS_SERVED && !MOCK_API ? (await roomApi.live()).map(meetingOfRoom) : [];
}

/**
 * Встречи раздела (домен `meetings`: его перечитывает и одобренное действие Leo): записи «Заметок» и, пока у meetings нет API, их образцы. Опрашивается, пока запись идёт или
 * её заметки пишутся, — так идущая встреча сама переходит в прошедшие с итогом Leo.
 */
export const meetingsResource = inDomain(
  "meetings",
  createPollingResource(
    async () => {
      const [plans, recorded, rooms] = await Promise.all([scheduled(), recordings(), liveRooms()]);
      return [...rooms, ...plans, ...recorded];
    },
    (meetings) => meetings.some((meeting) => meeting.recording?.busy === true || meeting.endless === true),
  ),
);

export const useMeetings = () => usePollingResource(meetingsResource);
