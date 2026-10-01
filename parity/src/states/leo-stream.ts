// Виджет Leo, ответ потоком и действия (шаг 5): ожидание, шаги, текст, подпись
// инструмента, остановка, ошибки, повтор ответа, картинка; карточки действий и
// их подтверждение. Ответы — потоки SSE черновика (api/agent.ts); идущий ответ —
// открытый поток.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { ACT, answer, ask, CHAT, chat, chatSideCalls, leo, openPanel, question, STREAM_REASON, type ChatMessage, type StorageFill } from "./leo-common.ts";
import { networkFailure, openStream, stream, type StreamEvent } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const step = (seq: number, activity: string, status = "started"): StreamEvent => ({
  event: "step",
  data: { id: `s${seq}`, seq, status, activity },
});
const token = (text: string): StreamEvent => ({ event: "token", data: { text } });
const DONE: StreamEvent = { event: "done", data: {} };
/** Картинка 1×1 PNG: виджет показывает её в figure с подписью. */
const PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

function streaming(id: string, events: readonly StreamEvent[], marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return leo(id, marker, { overrides: [...chatSideCalls, openStream("POST", CHAT, events, STREAM_REASON)], act: ask, ...extra });
}

function finished(id: string, events: readonly StreamEvent[], marker: (t: Translate) => string): State {
  return leo(id, marker, { overrides: [...chatSideCalls, stream("POST", CHAT, events, STREAM_REASON)], act: ask });
}

/** Предложенное действие в форме кадра `action` черновика (contracts/agent.ts). */
function proposal(extra: ChatMessage = {}): ChatMessage {
  return {
    type: "action_proposal",
    name: "create_note",
    args: { summary: "Создать заметку «Итоги бюджета»", text: "Бюджет Q4 утверждён с изменениями." },
    destructive: false,
    preview: "Заметка: «Итоги бюджета»\nТекст: Бюджет Q4 утверждён с изменениями.",
    needs_secret: false,
    secret_required: false,
    interrupt_id: "parity-interrupt",
    ...extra,
  };
}

const card = (action: ChatMessage, status: string): StorageFill =>
  chat([question("Сохрани итоги бюджета заметкой"), answer("", { action, actionStatus: status })]);

async function confirm(page: Page, context: StateContext): Promise<void> {
  await openPanel(page, context);
  await page.getByRole("button", { name: context.t("leo:agent.confirm"), exact: true }).click();
}

export const LEO_STREAM_STATES: readonly State[] = [
  streaming("chat.streaming.waiting", [], (t) => `button[aria-label=${JSON.stringify(t("leo:agent.stop"))}]`, { scope: "full" }),
  streaming("chat.streaming.steps", [step(1, "meetings")], () => "li.leo-step[data-status=started]"),
  streaming("chat.streaming.many-steps", [1, 2, 3, 4, 5, 6].map((seq) => step(seq, seq % 2 === 0 ? "web" : "meetings", "completed")),
    (t) => `button[aria-label=${JSON.stringify(t("leo:agent.ledger.expand"))}]`),
  streaming("chat.streaming.tokens", [token("Бюджет на четвёртый квартал утверждён. Офлайн-ивенты сокращаются на 30%,")],
    () => 'div.md-content:has-text("Офлайн-ивенты")'),
  streaming("chat.streaming.status-label", [token("Проверяю курс валют"), { event: "status", data: { phase: "tool", tool: "search_web" } }],
    (t) => exactText(t("leo:agent.statusSearchingWeb"))),
  streaming("chat.stopped", [token("Бюджет на четвёртый квартал")], () => 'div.md-content:has-text("Бюджет на четвёртый квартал")', {
    act: async (page, context) => {
      await ask(page, context);
      await page.locator('div.md-content:has-text("Бюджет на четвёртый квартал")').waitFor();
      await page.getByRole("button", { name: context.t("leo:agent.stop"), exact: true }).click();
    },
  }),
  finished("chat.done", [step(1, "meetings", "completed"), token("Встреча «Планирование бюджета Q4» утвердила бюджет с изменениями."), DONE],
    (t) => `button[aria-label=${JSON.stringify(t("leo:agent.regenerate"))}]`),
  // Код без своего текста: и черновик, и v2 показывают общий текст ошибки. Коды
  // со своим текстом черновик не переводит (находка в инвентаре) — вне эталона.
  finished("chat.error.stream", [{ event: "error", data: { code: "turn_deadline" } }, DONE],
    (t) => `.md-content:has-text(${JSON.stringify(t("errors:generic"))})`),
  leo("chat.error.connection", (t) => withText("div", t("errors:connection_lost")), {
    act: ask,
    overrides: [...chatSideCalls, networkFailure("POST", CHAT)],
  }),
  finished("chat.image", [token("Нарисовал схему:"), { event: "image", data: { mime: "image/png", data: PIXEL, alt: "Схема бюджета" } }, DONE],
    () => 'figure img[alt="Схема бюджета"]'),
  leo("chat.regenerating", (t) => `button[aria-label=${JSON.stringify(t("leo:agent.stop"))}]`, {
    storage: chat([question("Итоги бюджета"), answer("Бюджет утверждён.")]),
    overrides: [...chatSideCalls, openStream("POST", CHAT, [], STREAM_REASON)],
    act: async (page, context) => {
      await openPanel(page, context);
      await page.getByRole("button", { name: context.t("leo:agent.regenerate"), exact: true }).click();
    },
  }),
  leo("chat.action.proposed", (t) => withText("button", t("leo:agent.confirm")), { scope: "full", storage: card(proposal(), "proposed") }),
  leo("chat.action.destructive", (t) => exactText(t("leo:agent.destructiveWarn")), {
    storage: card(proposal({ name: "delete_meeting", args: { summary: "Удалить три старые встречи" }, destructive: true, preview: "Будет удалено: 3" }), "proposed"),
  }),
  leo("chat.action.secret", (t) => exactText(t("leo:agent.secretHint")), {
    storage: card(proposal({ name: "connect_integration", args: { summary: "Подключить Slack" }, needs_secret: true, secret_required: true, preview: null }), "proposed"),
  }),
  leo("chat.action.batch", (t) => exactText(t("leo:agent.actionBatch", { count: 3 })), {
    storage: card(proposal({ items: [
      { name: "create_tracker_task", args: { summary: "Подготовить смету по маркетингу" } },
      { name: "create_tracker_task", args: { summary: "Обновить прогноз выручки" } },
      { name: "create_tracker_task", args: { summary: "Согласовать бюджет с CFO" } },
    ] }), "proposed"),
  }),
  leo("chat.action.confirming", (t) => withText("button:disabled", t("leo:agent.confirm")), {
    storage: card(proposal(), "proposed"),
    overrides: [openStream("POST", ACT, [], STREAM_REASON)],
    act: confirm,
  }),
  leo("chat.action.done", (t) => exactText(t("leo:agent.done")), {
    storage: card(proposal(), "proposed"),
    overrides: [stream("POST", ACT, [{ event: "action_result", data: { ok: true, status: "done", result: {} } }, token("Заметка сохранена."), DONE], STREAM_REASON)],
    act: confirm,
  }),
  leo("chat.action.rejected", (t) => exactText(t("leo:agent.rejected")), { storage: card(proposal(), "rejected") }),
  leo("chat.action.expired", (t) => exactText(t("leo:agent.actionExpired")), { storage: card(proposal(), "expired") }),
];
