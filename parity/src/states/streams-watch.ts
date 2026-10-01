// Страница зрителя трансляции (шаг 6): имя, ссылка не работает, нужен аккаунт,
// эфир не начался или завершён, зал ожидания и отказ, эфир с чатом и рукой.
//
// Медиасервера у стенда нет: сцена остаётся в ожидании подключения (ошибки SFU
// страница зрителя не рисует). Всё остальное приходит по HTTP — из записи или
// правкой записанного состояния эфира.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { SEED_IDS } from "../recording/seed-ids.ts";
import { hold, reply } from "./overrides.ts";
import type { Override, State } from "./types.ts";

const STATE = "/v1/streams/live/state";
const JOIN = "/v1/streams/{token}/join";

const dockButton = (label: string): string => `.vroom-dock button[aria-label=${JSON.stringify(label)}]`;

function live(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `streams.watch.live.${id}`, fixture: "streams/watch-live", scope: "single", marker, ...extra };
}

function notice(id: string, fixture: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `streams.watch.${id}`, fixture: `streams/${fixture}`, scope: "single", marker, ...extra };
}

/** Заявка гостя на вход: страница хранит её токен в sessionStorage. */
const knock = (key: string): Readonly<Record<string, string>> =>
  ({ [`wh.stream.knock.${SEED_IDS.streamInvites["live"] ?? ""}`]: SEED_IDS.knocks[key] ?? "" });

const liveState = (patch: { readonly [key: string]: JsonValue }, reason: string): Override =>
  ({ method: "GET", path: STATE, reason, respond: { merge: patch } });

async function sendChat(page: Page, t: Translate): Promise<void> {
  const input = page.getByPlaceholder(t("streams:stream.chat.placeholder"), { exact: true });
  await input.fill("Будет ли запись эфира?");
  await input.press("Enter");
}

export const STREAMS_WATCH_STATES: readonly State[] = [
  notice("name-required", "watch-name", (t) => exactText(t("streams:stream.join.title")), { scope: "full" }),
  notice("broken", "watch-name", (t) => exactText(t("streams:stream.notice.brokenTitle")), {
    overrides: [reply("GET", "/v1/streams/{token}", 404, { detail: "not_found" }, "ссылку на засеянную трансляцию черновик находит")],
  }),
  notice("loading", "watch-live", () => "svg.spin", { overrides: [hold("POST", JOIN)] }),
  notice("registration-required", "watch-members", (t) => exactText(t("streams:stream.notice.accountTitle"))),
  notice("not-live", "watch-soon", (t) => exactText(t("streams:stream.notice.soonTitle"))),
  notice("ended", "watch-ended", (t) => exactText(t("streams:stream.notice.endedArchiveText")), { scope: "full" }),
  notice("ended.no-archive", "watch-ended", (t) => exactText(t("streams:stream.notice.endedArchiveText")), {
    overrides: [{ method: "POST", path: JOIN, reason: "у засеянного эфира чат сохранён", respond: { merge: { card: { chat_archived: false } } } }],
  }),
  notice("waiting", "watch-wait", (t) => exactText(t("streams:stream.notice.waitingTitle")), { session: knock("wait") }),
  notice("denied", "watch-denied", (t) => exactText(t("streams:stream.notice.deniedTitle")), { session: knock("denied") }),

  live("audience", (t) => dockButton(t("rooms:meeting.stream.lowerHand")), { scope: "full" }),
  live("hand-down", (t) => dockButton(t("rooms:meeting.stream.raiseHand")), {
    overrides: [liveState({ my_request: null }, "у засеянного зрителя рука поднята")],
  }),
  live("reactions", (t) => `.vroom-pop button[aria-label=${JSON.stringify(`${t("rooms:meeting.reactions.title")}: 👍`)}]`, {
    act: async (page, { t }) => page.locator(dockButton(t("rooms:meeting.reactions.title"))).click(),
  }),
  live("chat-off", (t) => exactText(t("streams:stream.chat.disabled")), {
    overrides: [liveState({ chat_mode: "off" }, "у засеянного эфира чат открыт всем")],
  }),
  live("chat-banned", (t) => exactText(t("streams:stream.chat.errBanned")), {
    overrides: [reply("POST", "/v1/streams/live/chat", 403, { detail: "chat_banned" }, "засеянного зрителя в чате не блокировали")],
    act: async (page, { t }) => sendChat(page, t),
  }),
  live("chat-too-fast", (t) => exactText(t("streams:stream.chat.errTooFast")), {
    overrides: [reply("POST", "/v1/streams/live/chat", 429, { detail: "too_fast" }, "запись стенда не писала в чат дважды подряд")],
    act: async (page, { t }) => sendChat(page, t),
  }),
  live("on-stage", (t) => dockButton(t("streams:stream.stage.leave")), {
    overrides: [liveState({ role: "speaker" }, "засеянного зрителя на сцену не звали")],
  }),
  live("ended-by-host", (t) => withText("button", t("streams:stream.notice.reload")), {
    overrides: [liveState({ status: "ended" }, "засеянный эфир идёт")],
  }),
  live("left", (t) => exactText(t("streams:stream.notice.leftTitle")), {
    act: async (page, { t }) => page.locator(dockButton(t("rooms:meeting.ctl.leave"))).click(),
  }),
];
