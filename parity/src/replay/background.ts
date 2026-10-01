// Фоновые запросы оболочки, которые могут прийти позже, чем закончилась запись
// визита: их ответы на экране не видны. Если фикстура их не содержит, отвечаем
// заданным здесь ответом. Список короткий и закрытый: всё остальное без
// фикстуры — ошибка состояния, а не повод отвечать «что-нибудь».

import type { OverrideResponse } from "../states/types.ts";

interface BackgroundResponse extends OverrideResponse {
  readonly reason: string;
}

export const BACKGROUND: ReadonlyMap<string, BackgroundResponse> = new Map([
  [
    "POST /v1/analytics/collect",
    { status: 204, body: null, reason: "продуктовая аналитика: отправка раз в 5 с, ответ не используется" },
  ],
  [
    "POST /v1/satisfaction/prompt",
    {
      status: 200,
      body: { due: false, survey_id: null, next_due_at: null },
      reason: "опрос удовлетворённости запрашивается через 25 с после открытия; due=false — карточки нет, как в записях",
    },
  ],
  ["GET /v1/health", { status: 200, body: { status: "ok" }, reason: "проба соединения после сетевой ошибки" }],
]);
