// Общее для состояний виджета Leo: открытие панели, переписка в localStorage,
// отправка сообщения, адреса потоков.
//
// Переписка живёт в браузере (agent-chat-v1:<id пользователя>), поэтому её
// засевает состояние, а не сервер. id беседы задан явно: иначе виджет взял бы
// случайный UUID.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import type { Translate } from "../i18n/texts.ts";
import { reply } from "./overrides.ts";
import type { State, StateContext, StorageSeed } from "./types.ts";

export const CHAT = "/v1/ai/agent/chat";
export const ACT = "/v1/ai/agent/act";
export const LEO_HOME = "leo/home";
export const STREAM_REASON = "ответ Leo собирает модель, которой на стенде нет";

/** Реплика переписки в форме, которую хранит виджет (contracts/chat.ts черновика). */
export type ChatMessage = { readonly [key: string]: JsonValue };

export const launcher = (t: Translate): string => `button[aria-label=${JSON.stringify(t("leo:agent.open"))}]`;
export const composer = (t: Translate): string => `textarea[aria-label=${JSON.stringify(t("leo:meet.chat.messageAria"))}]`;

export async function openPanel(page: Page, { t }: StateContext): Promise<void> {
  await page.locator(launcher(t)).click();
  await page.locator(composer(t)).waitFor();
}

/** Открыть панель, набрать вопрос и отправить. */
export async function ask(page: Page, context: StateContext, text = "Подведи итоги встречи по бюджету"): Promise<void> {
  await openPanel(page, context);
  await page.locator(composer(context.t)).fill(text);
  await page.keyboard.press("Enter");
}

/** Ключи localStorage, которые состояние кладёт по id пользователя фикстуры. */
export type StorageFill = (seed: StorageSeed) => Record<string, string>;

/** Ключи localStorage с перепиской и id беседы. */
export function chat(messages: readonly ChatMessage[]): StorageFill {
  return ({ userId }) => ({
    [`agent-chat-v1:${userId}`]: JSON.stringify(messages),
    [`agent-session-v1:${userId}`]: "parity-session",
  });
}

export const question = (text: string, extra: ChatMessage = {}): ChatMessage => ({ id: "u1", role: "user", content: text, ...extra });
export const answer = (text: string, extra: ChatMessage = {}): ChatMessage => ({ id: "a1", role: "assistant", content: text, ...extra });

/** Разогрев агента при первом фокусе поля и отметка пункта «Первый вопрос» после ответа. */
export const chatSideCalls = [
  reply("POST", "/v1/ai/agent/prewarm", 204, null, "разогрев модели агента; моделей на стенде нет"),
  reply("POST", "/v1/me/onboarding/progress", 200, {
    status: "completed",
    audio_status: "declined",
    version: 1,
    current_step: null,
    completed_steps: [],
    done_actions: ["first_question"],
    started_at: "2026-03-19T12:00:00Z",
    completed_at: "2026-03-19T12:20:00Z",
  }, "ответ Leo отмечает пункт «Первый вопрос» чек-листа"),
];

type Act = NonNullable<State["act"]>;

/** Состояние панели Leo на домашней странице «руководителя». */
export function leo(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  const act: Act = extra.act ?? openPanel;
  return { id: `leo.${id}`, fixture: LEO_HOME, scope: "single", ...extra, act, marker };
}
