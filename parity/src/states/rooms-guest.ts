// Гостевой вход в комнату и раздел администратора LiveKit (шаг 6).
//
// Раздел LiveKit черновик пишет по-русски без переводов, поэтому маркеры —
// строки, а не ключи. Здоровье, нагрузку и участников отдаёт сервер LiveKit,
// которого у стенда нет: ответы синтетика; записи и журнал — из базы черновика.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, type Translate } from "../i18n/texts.ts";
import { hold, reply, serverError } from "./overrides.ts";
import { CAMERA_MASK, connectError } from "./rooms.ts";
import type { Override, State, StateContext } from "./types.ts";

const JOIN = "/v1/rooms/join/{invite}";
const HEALTH = "/v1/admin/livekit/health";
const STATS = "/v1/admin/livekit/stats";
const ROOM_DETAIL = "/v1/admin/livekit/rooms/{lk_room}";
const EGRESS = "/v1/admin/livekit/egress";
const LIVEKIT_REASON = "это отдаёт сервер LiveKit; на стенде его нет";
/** Момент стенда, 2026-07-17 12:00 UTC, в секундах: так время отдаёт LiveKit. */
const NOW = 1_784_289_600;

async function joinAsGuest(page: Page, { t }: StateContext): Promise<void> {
  await page.getByLabel(t("rooms:rooms.yourName"), { exact: true }).fill("Гость Acme");
  await page.getByRole("button", { name: t("rooms:meeting.prejoin.join"), exact: true }).click();
}

function guest(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `rooms.guest.${id}`, fixture: "rooms/guest", scope: "single", marker, ...extra };
}

function livekit(id: string, marker: () => string, extra: Partial<State> = {}): State {
  return { id: `livekit.${id}`, fixture: "admin/livekit", scope: "single", marker, ...extra };
}

const merged = (path: string, patch: { readonly [key: string]: JsonValue }, reason: string): Override =>
  ({ method: "GET", path, reason, respond: { merge: patch } });

const track = (source: string, muted: boolean): JsonValue => ({
  sid: `TR_${source}`,
  source,
  type: source === "MICROPHONE" ? "AUDIO" : "VIDEO",
  muted,
  width: source === "CAMERA" ? 1280 : 0,
  height: source === "CAMERA" ? 720 : 0,
});

const participant = (identity: string, name: string, minutes: number, extra: { [key: string]: JsonValue }): JsonValue => ({
  sid: `PA_${identity}`,
  identity,
  name,
  state: "ACTIVE",
  joined_at: NOW - minutes * 60,
  is_publisher: true,
  region: "eu-central",
  can_publish: true,
  is_service: false,
  hidden: false,
  tracks: [],
  ...extra,
});

/** Созвон с Acme: ведущая, гость с выключенной камерой, бот записи и зритель стрима. */
const ACME_DETAIL: Override = reply("GET", ROOM_DETAIL, 200, {
  lk_room: "r-parity-acme",
  domain: null,
  orphan: false,
  participants: [
    participant("00000000-0000-4000-8000-0000000000ff__0000beef", "Мария Соколова", 24, { tracks: [track("CAMERA", false), track("MICROPHONE", false)] }),
    participant("guest-0123456789ab", "Гость Acme", 12, { tracks: [track("CAMERA", true), track("MICROPHONE", false)] }),
    participant("EG_parity_live", "", 20, { is_publisher: false, can_publish: false, is_service: true }),
    participant("guest-5eed00000009", "Зритель", 5, { is_publisher: false, can_publish: false, hidden: true }),
  ],
  egress: [],
}, LIVEKIT_REASON);

const expand = async (page: Page): Promise<void> => {
  await page.locator('button[aria-label="Участники комнаты Созвон с Acme"]').click();
};

const ACTIVE_EGRESS = merged(EGRESS, {
  available: true,
  active: [{
    egress_id: "EG_parity_live",
    room_name: "r-parity-acme",
    status: "EGRESS_ACTIVE",
    started_at: NOW - 20 * 60,
    ended_at: 0,
    error: null,
    filename: null,
    size: null,
    duration_seconds: null,
  }],
}, "идущие записи отдаёт egress LiveKit; на стенде его нет");

export const ROOMS_GUEST_STATES: readonly State[] = [
  guest("prejoin", (t) => `input[aria-label=${JSON.stringify(t("rooms:rooms.yourName"))}]`, { scope: "full", mask: CAMERA_MASK }),
  guest("joining", () => "button:has(svg.spin)", { mask: CAMERA_MASK, overrides: [hold("POST", JOIN)], act: joinAsGuest }),
  guest("unavailable", (t) => exactText(t("rooms:rooms.joinError")), { mask: CAMERA_MASK, overrides: [serverError("POST", JOIN)], act: joinAsGuest }),
  guest("in-room", connectError, { act: joinAsGuest }),
  { id: "rooms.guest.finished", fixture: "rooms/guest-finished", scope: "single", marker: (t) => exactText(t("rooms:rooms.joinFinished")), act: joinAsGuest },

  livekit("health.ok", () => 'text="Журнал вмешательств"'),
  livekit("loading", () => "svg.spin", { overrides: [hold("GET", HEALTH)] }),
  livekit("health.down", () => 'text="SFU недоступен"', {
    overrides: [reply("GET", HEALTH, 200, { status: "down", checked_at: "2026-07-17T12:00:00+00:00", detail: "not_configured", recording_available: false },
      "ответ черновика без ключей LiveKit; стенд записи работает с поддельными ключами")],
  }),
  livekit("health.load-warn", () => 'text="82%"', { overrides: [merged(STATS, { load_pct: 82 }, "нагрузку узла отдаёт LiveKit")] }),
  livekit("health.recording-off", () => 'text="запись выключена"', { overrides: [merged(HEALTH, { recording_available: false }, LIVEKIT_REASON)] }),
  livekit("rooms.loading", () => 'text="Активные комнаты"', { overrides: [hold("GET", STATS)] }),
  livekit("rooms.empty", () => 'text="Активных комнат нет."', {
    overrides: [merged(STATS, { active_rooms: 0, total_participants: 0, total_publishers: 0, total_subscriptions: 0, active_recordings: 0, load_pct: 0, rooms: [] }, LIVEKIT_REASON)],
  }),
  livekit("room.expanded", () => 'text="бот записи"', { overrides: [ACME_DETAIL], act: expand }),
  livekit("room.expanded-loading", () => 'tr:has(button[aria-label="Участники комнаты Созвон с Acme"]) + tr svg.spin', {
    overrides: [hold("GET", ROOM_DETAIL)],
    act: expand,
  }),
  livekit("room.expanded-empty", () => 'text="В комнате никого нет."', {
    overrides: [reply("GET", ROOM_DETAIL, 200, { lk_room: "r-parity-acme", domain: null, orphan: false, participants: [], egress: [] }, LIVEKIT_REASON)],
    act: expand,
  }),
  livekit("room.expanded-error", () => 'text="Не удалось получить участников комнаты."', { overrides: [serverError("GET", ROOM_DETAIL)], act: expand }),
  livekit("room.close-confirm", () => 'dialog[aria-label="Завершить комнату"]', {
    act: async (page) => page.getByRole("button", { name: "Завершить", exact: true }).first().click(),
  }),
  livekit("participant.kick-confirm", () => 'dialog[aria-label="Отключить участника"]', {
    overrides: [ACME_DETAIL],
    act: async (page) => {
      await expand(page);
      await page.locator('button[aria-label="Отключить Гость Acme"]').click();
    },
  }),
  livekit("egress.active", () => 'text="идёт"', { reveal: true, overrides: [ACTIVE_EGRESS] }),
  livekit("egress.stuck", () => 'text="Зависшие записи"', { reveal: true, overrides: [ACTIVE_EGRESS] }),
  livekit("audit", () => 'text="SFU не ответил"', { reveal: true }),
  livekit("egress.stop-confirm", () => 'dialog[aria-label="Остановить запись"]', {
    overrides: [ACTIVE_EGRESS],
    act: async (page) => page.locator('button[aria-label="Остановить запись комнаты r-parity-acme"]').click(),
  }),
  livekit("audit.empty", () => 'text="Админы ещё не вмешивались в чужие звонки — журнал пуст."', {
    reveal: true,
    overrides: [reply("GET", "/v1/admin/livekit/audit", 200, [], "у засеянного раздела есть журнал вмешательств")],
  }),
];
