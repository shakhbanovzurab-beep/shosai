// Визиты видеокомнат, трансляций и раздела LiveKit. Состояния —
// parity/inventory/rooms-streams-storage-tracker.md.
//
// Медиасервер браузеру недоступен: сокет LiveKit запись закрывает, и комната
// остаётся «не удалось подключиться». Экраны с живым видео вне матрицы (решение 3
// плана D2); всё, что страница рисует по HTTP, визит записывает.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../../fixtures/format.ts";
import { exactText, withText, type Translate } from "../../i18n/texts.ts";
import { roomUrl, SEED_IDS, studioUrl } from "../seed-ids.ts";
import type { Visit, VisitContext, VisitStub } from "./types.ts";

const STREAM_NAME = "wh.stream.name";
const knockKey = (invite: string): string => `wh.stream.knock.${invite}`;
const liveUrl = (key: string): string => `/app/live/${SEED_IDS.streamInvites[key] ?? ""}`;

const prejoinTitle = (t: Translate): string => withText("h1", t("rooms:meeting.prejoin.join"));
const connectError = (t: Translate): string => exactText(t("rooms:rooms.connectError"));

/** Войти из предпросмотра в комнату: кнопка с тем же текстом, что заголовок. */
async function join(page: Page, { t }: VisitContext): Promise<void> {
  await page.locator(prejoinTitle(t)).waitFor();
  await page.getByRole("button", { name: t("rooms:meeting.prejoin.join"), exact: true }).click();
}

async function joinAsGuest(page: Page, context: VisitContext): Promise<void> {
  await page.getByLabel(context.t("rooms:rooms.yourName"), { exact: true }).fill("Гость Acme");
  await join(page, context);
}

const LIVEKIT_REASON = "здоровье и статистику отдаёт сервер LiveKit; на стенде его нет";
const domain = (room: string, title: string, recording: boolean): JsonValue => ({
  room_id: SEED_IDS.rooms[room] ?? "",
  title,
  owner_email: "lead@parity.test",
  owner_id: "00000000-0000-4000-8000-0000000000ff",
  status: "active",
  e2ee: room === "e2ee",
  recording_enabled: recording,
  max_participants: 0,
  created_at: "2026-07-14T12:00:00Z",
});
const lkRoom = (name: string, participants: number, publishers: number, recording: boolean, room: JsonValue | null): JsonValue => ({
  name,
  sid: `RM_${name}`,
  num_participants: participants,
  num_publishers: publishers,
  max_participants: 0,
  subscriptions: participants * publishers,
  creation_time: 1_784_288_400,
  active_recording: recording,
  domain: room,
  orphan: room === null,
});

/** Раздел LiveKit: сервер здоров, идут две комнаты и сирота; записи и журнал — из базы черновика. */
const LIVEKIT_STUBS: readonly VisitStub[] = [
  {
    method: "GET",
    path: "/v1/admin/livekit/health",
    status: 200,
    body: { status: "ok", checked_at: "2026-07-17T12:00:00+00:00", recording_available: true },
    reason: LIVEKIT_REASON,
  },
  {
    method: "GET",
    path: "/v1/admin/livekit/stats",
    status: 200,
    body: {
      active_rooms: 3,
      total_participants: 7,
      total_publishers: 5,
      total_subscriptions: 14,
      active_recordings: 1,
      soft_subscription_capacity: 1440,
      load_pct: 12,
      rooms: [
        lkRoom("r-parity-acme", 4, 3, true, domain("acme", "Созвон с Acme", true)),
        lkRoom("r-parity-e2ee", 2, 2, false, domain("e2ee", "Юристы (E2EE)", false)),
        lkRoom("r-orphan-7f3c", 1, 0, false, null),
      ],
    },
    reason: LIVEKIT_REASON,
  },
];

/** Пульт студии открыт по умолчанию; список зала черновик перезапрашивает без конца. */
const STUDIO_HOLD = ["GET /v1/streams/live/audience"];

export const ROOMS_VISITS: readonly Visit[] = [
  { id: "rooms/host", persona: "lead", url: roomUrl("acme"), marker: connectError, act: join },
  { id: "rooms/host-e2ee", persona: "lead", url: roomUrl("e2ee"), marker: connectError, act: join },
  { id: "rooms/host-closed", persona: "lead", url: roomUrl("closed"), marker: (t) => exactText(t("rooms:rooms.finishedTitle")) },
  { id: "rooms/host-anonymous", persona: null, url: roomUrl("acme"), marker: (t) => exactText(t("rooms:rooms.signInTitle")) },
  { id: "rooms/guest", persona: null, url: `/app/rooms/join/${SEED_IDS.roomInvite}`, marker: connectError, act: joinAsGuest },
  {
    id: "rooms/guest-finished",
    persona: null,
    url: `/app/rooms/join/${SEED_IDS.roomInvites["closed"] ?? ""}`,
    marker: (t) => exactText(t("rooms:rooms.finishedTitle")),
    act: joinAsGuest,
  },
  {
    // Раздел администратора черновик пишет без переводов.
    id: "admin/livekit",
    persona: "admin",
    url: "/app/admin/livekit",
    stubs: LIVEKIT_STUBS,
    marker: () => 'text="Журнал вмешательств"',
  },

  { id: "streams/watch-name", persona: null, url: liveUrl("live"), marker: (t) => exactText(t("streams:stream.join.title")) },
  {
    id: "streams/watch-live",
    persona: "pro",
    url: liveUrl("live"),
    marker: (t) => `button[aria-label=${JSON.stringify(t("rooms:meeting.stream.lowerHand"))}]`,
  },
  {
    id: "streams/watch-wait",
    persona: null,
    url: liveUrl("live"),
    storage: { [STREAM_NAME]: "Гость" },
    session: { [knockKey(SEED_IDS.streamInvites["live"] ?? "")]: SEED_IDS.knocks["wait"] ?? "" },
    marker: (t) => exactText(t("streams:stream.notice.waitingTitle")),
  },
  {
    id: "streams/watch-denied",
    persona: null,
    url: liveUrl("live"),
    storage: { [STREAM_NAME]: "Гость" },
    session: { [knockKey(SEED_IDS.streamInvites["live"] ?? "")]: SEED_IDS.knocks["denied"] ?? "" },
    marker: (t) => exactText(t("streams:stream.notice.deniedTitle")),
  },
  { id: "streams/watch-soon", persona: "free", url: `/app/live/${SEED_IDS.streamInvite}`, marker: (t) => exactText(t("streams:stream.notice.soonTitle")) },
  { id: "streams/watch-ended", persona: "free", url: liveUrl("ended"), marker: (t) => exactText(t("streams:stream.notice.endedTitle")) },
  {
    id: "streams/watch-members",
    persona: null,
    url: liveUrl("members"),
    storage: { [STREAM_NAME]: "Гость" },
    marker: (t) => exactText(t("streams:stream.notice.accountTitle")),
  },
  { id: "streams/studio", persona: "lead", url: studioUrl("live"), hold: STUDIO_HOLD, marker: (t) => exactText(t("streams:stream.studio.rulesTitle")) },
  {
    id: "streams/studio-scheduled",
    persona: "lead",
    url: studioUrl("quarter"),
    hold: STUDIO_HOLD,
    marker: (t) => withText("button", t("streams:stream.studio.start")),
  },
];
