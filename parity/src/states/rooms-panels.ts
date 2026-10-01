// Панели комнаты ведущего (шаг 6): переводчик, AI-ассистент и запись встречи.
//
// Распознавание речи браузера заглушено (determinism/page-setup.ts): ассистент
// «слушает», но реплик нет. Ответ ассистента и запуск записи требуют модели и
// SFU — их ответы синтетика; список записей черновик отдаёт из базы.

import type { Page } from "@playwright/test";

import { withText, type Translate } from "../i18n/texts.ts";
import { hold, reply } from "./overrides.ts";
import { join, moreItem, panel } from "./rooms.ts";
import type { Override, State, StateContext } from "./types.ts";

const ASK = "/v1/meeting-ai/ask";
const RECORDINGS = "/v1/me/rooms/{id}/recordings";
const ROOM_ID = "00000000-0000-4000-8000-000000000003";
const MODEL_REASON = "ответ ассистента пишет модель; на стенде её нет";
const SFU_REASON = "запись ведёт egress медиасервера; на стенде его нет";

function room(id: string, marker: State["marker"], extra: Partial<State> = {}): State {
  return { id: `rooms.room.${id}`, fixture: "rooms/host", scope: "single", marker, ...extra };
}

const openTranslator = moreItem((t) => t("rooms:meeting.translator.title"));
const openAi = moreItem((t) => t("rooms:meeting.ai.title"));

async function ask(page: Page, context: StateContext): Promise<void> {
  await openAi(page, context);
  const input = page.getByLabel(context.t("rooms:meeting.ai.ask.placeholder"), { exact: true });
  await input.fill("Что решили по SSO?");
  await input.press("Enter");
}

const askReply = (status: number, detail: string): Override =>
  reply("POST", ASK, status, { detail }, MODEL_REASON);

/** Идущая запись: egress запущен 5 минут назад. */
const RECORDING = {
  id: "00000000-0000-4000-8000-0000000000a1",
  room_id: ROOM_ID,
  status: "recording",
  size: 0,
  duration_seconds: null,
  session_id: null,
  storage_file_id: null,
  created_at: "2026-07-17T11:55:00Z",
  updated_at: "2026-07-17T11:55:00Z",
};
const ACTIVE: Override = reply("GET", RECORDINGS, 200, [RECORDING], SFU_REASON);

/**
 * Остановка принята, а запись ещё числится идущей: ждём вебхук egress. После
 * остановки комната сохраняет доску в файлы — у пустой доски сохранять нечего.
 */
const STOPPED: readonly Override[] = [
  reply("POST", "/v1/me/rooms/{id}/recording/stop", 202, { stopped: true, recording: RECORDING }, SFU_REASON),
  reply("GET", "/v1/whiteboard/scene", 200, { room_id: ROOM_ID, elements: [], files: {}, version: 0, updated_at: null, storable: true },
    "доску комнаты читают по пропуску медиасервера; у стенда его нет"),
];

const record = (label: (t: Translate) => string) => async (page: Page, context: StateContext): Promise<void> => {
  await join(page, context);
  await page.locator(`.vroom-rec[aria-label=${JSON.stringify(label(context.t))}]`).click();
};

export const ROOMS_PANEL_STATES: readonly State[] = [
  room("translator.off", (t) => withText(panel(t("rooms:meeting.translator.title")), t("rooms:meeting.translator.sameLangHint")), {
    act: openTranslator,
  }),
  room("translator.lang-differ", (t) => withText(panel(t("rooms:meeting.translator.title")), t("rooms:meeting.translator.languagesHint")), {
    act: async (page, context) => {
      await openTranslator(page, context);
      // Список из 16 языков — выбор с поиском: кнопка-триггер и варианты.
      await page.locator(`button[aria-label=${JSON.stringify(context.t("rooms:meeting.translator.sourceLabel"))}]`).click();
      await page.getByRole("option", { name: "English", exact: true }).click();
    },
  }),
  room("translator.on-idle", (t) => withText(panel(t("rooms:meeting.translator.title")), t("rooms:meeting.translator.statusIdle")), {
    act: async (page, context) => {
      await openTranslator(page, context);
      await page.getByRole("button", { name: context.t("rooms:meeting.translator.off"), exact: true }).click();
    },
  }),
  room("ai.listening", (t) => withText(panel(t("rooms:meeting.ai.title")), t("rooms:meeting.ai.empty")), { scope: "full", act: openAi }),
  room("ai.thinking", (t) => withText(panel(t("rooms:meeting.ai.title")), t("rooms:meeting.ai.ask.thinking")), {
    overrides: [hold("POST", ASK)],
    act: ask,
  }),
  room("ai.answer", () => 'text="SSO через Azure AD подключаем после согласования с безопасностью."', {
    overrides: [reply("POST", ASK, 200, {
      answer: "SSO через Azure AD подключаем после согласования с безопасностью.",
      model: "Claude Sonnet 5.5",
    }, MODEL_REASON)],
    act: ask,
  }),
  room("ai.error-subscription", (t) => withText(panel(t("rooms:meeting.ai.title")), t("rooms:meeting.ai.ask.subscription")), {
    overrides: [askReply(403, "meeting_ai_subscription_required")],
    act: ask,
  }),
  room("ai.error-too-often", (t) => withText(panel(t("rooms:meeting.ai.title")), t("rooms:meeting.ai.ask.tooOften")), {
    overrides: [reply("POST", ASK, 429, { error: "Rate limit exceeded: 10 per 1 minute" }, "лимиты на стенде записи выключены")],
    act: ask,
  }),
  room("ai.error", (t) => withText(panel(t("rooms:meeting.ai.title")), t("rooms:meeting.ai.ask.error")), {
    overrides: [askReply(502, "meeting_ai_failed")],
    act: ask,
  }),

  room("record.busy", () => ".vroom-rec:disabled svg.spin", {
    overrides: [hold("POST", "/v1/me/rooms/{id}/recording/start")],
    act: record((t) => t("rooms:rooms.record.start")),
  }),
  room("record.active", (t) => `.vroom-rec[aria-label=${JSON.stringify(t("rooms:rooms.record.stop"))}]`, {
    overrides: [ACTIVE],
    act: join,
  }),
  room("record.stopping", (t) => `.vroom-rec[aria-label=${JSON.stringify(t("rooms:rooms.record.stopping"))}]`, {
    overrides: [ACTIVE, ...STOPPED],
    act: record((t) => t("rooms:rooms.record.stop")),
  }),
  room("record.error-toast", (t) => withText("[role=alert]", t("rooms:rooms.record.error")), {
    expectsAlert: true,
    overrides: [reply("POST", "/v1/me/rooms/{id}/recording/start", 503, { detail: "recording_unavailable" }, SFU_REASON)],
    act: record((t) => t("rooms:rooms.record.start")),
  }),
];
