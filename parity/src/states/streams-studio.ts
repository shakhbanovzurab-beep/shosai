// Пульт ведущего трансляции (шаг 6): загрузка, стрим недоступен, эфир не начат
// и идёт, подтверждение конца эфира, разделы пульта, чат и сбои действий.
//
// Список зала черновик перезапрашивает без конца, пока открыт пульт (эффект
// зависит от объекта, который создаётся заново на каждом рендере). Поэтому на
// него один ответ, а следующие запросы висят: экран тот же, что видит ведущий
// между ответами. Зал без SFU у черновика всегда пуст — зрители синтетика.

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { Override, State } from "./types.ts";

const AUDIENCE = "/v1/streams/live/audience";
const OVERVIEW = "/v1/me/streams/{id}";

const audience = (viewers: readonly JsonValue[], reason: string): Override =>
  ({ method: "GET", path: AUDIENCE, respond: [{ status: 200, body: [...viewers] }, "hold"], reason });

/** Зал, как его отдаёт черновик без медиасервера: пустой. */
const EMPTY_HALL = audience([], "зал черновик спрашивает без конца: первый ответ — пустой, как без SFU, следующие висят");

/** Зритель зала: по умолчанию гость по ссылке из России. */
const viewer = (identity: string, name: string, extra: { [key: string]: JsonValue }): JsonValue => ({
  identity,
  principal: identity,
  name,
  user_id: null,
  joined_at: "2026-07-17T11:40:00Z",
  country: "RU",
  language: "ru",
  plan: null,
  plan_active: false,
  role: null,
  ...extra,
});

const HALL = audience([
  viewer("guest-5eed0000000a", "Анна", {}),
  viewer("00000000-0000-4000-8000-0000000000b1__0000beef", "Егор Волков", {
    principal: "00000000-0000-4000-8000-0000000000b1",
    user_id: "00000000-0000-4000-8000-0000000000b1",
    joined_at: "2026-07-17T11:38:00Z",
    country: "DE",
    language: "en",
    plan: "pro_1m",
    plan_active: true,
  }),
  viewer("00000000-0000-4000-8000-0000000000b2__0000cafe", "Игорь", {
    principal: "00000000-0000-4000-8000-0000000000b2",
    user_id: "00000000-0000-4000-8000-0000000000b2",
    joined_at: "2026-07-17T11:45:00Z",
    country: "KZ",
    plan: "pro_1m",
  }),
], "зрителей зала знает только медиасервер; у стенда его нет, а следующие запросы висят");

const dockButton = (label: string): string => `.vroom-dock button[aria-label=${JSON.stringify(label)}]`;

function studio(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  const { overrides = [], ...rest } = extra;
  return { id: `streams.studio.${id}`, fixture: "streams/studio", scope: "single", marker, overrides: [EMPTY_HALL, ...overrides], ...rest };
}

function scheduled(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return studio(id, marker, { fixture: "streams/studio-scheduled", ...extra });
}

export const STREAMS_STUDIO_STATES: readonly State[] = [
  studio("on-air", (t) => dockButton(t("streams:stream.studio.end")), { scope: "full" }),
  studio("loading", () => "svg.spin", { overrides: [hold("GET", OVERVIEW)] }),
  studio("unavailable", (t) => exactText(t("streams:stream.studio.unreachable")), {
    overrides: [reply("GET", OVERVIEW, 404, { detail: "not_found" }, "засеянный стрим принадлежит ведущей")],
  }),
  scheduled("off-air", (t) => withText("button", t("streams:stream.studio.start"))),
  studio("confirm-end", (t) => `dialog[aria-label=${JSON.stringify(t("streams:stream.studio.confirmEndTitle"))}]`, {
    act: async (page, { t }) => page.locator(dockButton(t("streams:stream.studio.end"))).click(),
  }),
  studio("panel.hall", () => 'text="Егор Волков" >> nth=-1', {
    reveal: true,
    overrides: [HALL],
  }),
  studio("panel.rules", (t) => exactText(t("streams:stream.studio.saveChatLabel")), { reveal: true }),
  studio("panel.failure", (t) => exactText(t("streams:stream.studio.errGeneric")), {
    overrides: [serverError("POST", "/v1/streams/live/admissions/{id}")],
    act: async (page, { t }) => page.getByRole("button", { name: t("streams:stream.studio.admit"), exact: true }).first().click(),
  }),
  studio("chat", (t) => exactText(t("streams:stream.chat.title")), {
    act: async (page, { t }) => page.locator(dockButton(t("streams:stream.chat.title"))).click(),
  }),
  scheduled("start-failed", (t) => withText("[role=alert]", t("streams:stream.studio.startFailed")), {
    expectsAlert: true,
    overrides: [serverError("POST", "/v1/me/streams/{id}/start")],
    act: async (page, { t }) => page.getByRole("button", { name: t("streams:stream.studio.start"), exact: true }).click(),
  }),
];
