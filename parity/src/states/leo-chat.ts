// Виджет Leo, панель и переписка (шаг 5): кнопка, пустая панель, весь экран,
// переписка из localStorage — разметка, код, формулы, диаграмма, вложения, ход работы.

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { answer, chat, leo, launcher, openPanel, question, type ChatMessage, type StorageFill } from "./leo-common.ts";
import type { State } from "./types.ts";

const MARKDOWN = `## Итоги недели

Встреч: **5**, из них с клиентами — 2.

- Бюджет Q4 утверждён с изменениями
- Найм: две вакансии на паузе

| Встреча | Длительность |
|---|---|
| Планирование бюджета Q4 | 47 мин |
| Синк команды разработки | 32 мин |

Подробности — в [библиотеке встреч](https://whisperer.one/app/meetings).`;

const CODE = "Вот функция:\n\n```ts\nexport function total(minutes: number[]): number {\n  return minutes.reduce((sum, value) => sum + value, 0);\n}\n```";
const LONG_CODE = `Полный список:\n\n\`\`\`ts\n${Array.from({ length: 26 }, (_, index) => `const meeting${index + 1} = "Встреча ${index + 1}";`).join("\n")}\n\`\`\``;
const MATH = "Формула роста выручки: $$R_{q} = R_{q-1} \\cdot (1 + g)$$ где $g$ — темп роста.";
const MERMAID = "Схема процесса:\n\n```mermaid\ngraph TD\n  A[Встреча] --> B[Заметки]\n  B --> C[Задачи]\n```";

/** Ход работы: шаги поиска с исходом. Время — из длительностей, а не из часов. */
function steps(status: string, extra: ChatMessage = {}): ChatMessage[] {
  return [
    { id: "s1", seq: 1, status: "completed", activity: "meetings", startedAt: 1_784_289_600_000, endedAt: 1_784_289_602_100, durationMs: 2100 },
    { id: "s2", seq: 2, status, activity: "web", startedAt: 1_784_289_602_100, endedAt: 1_784_289_604_200, durationMs: 2100, ...extra },
  ];
}

const withSteps = (status: string, extra: ChatMessage = {}): StorageFill =>
  chat([question("Что нового по Acme?"), answer("Нашёл две встречи с Acme на этой неделе.", { steps: steps(status, extra) })]);

const ledger = (t: Translate): string => `[role=group][aria-label=${JSON.stringify(t("leo:agent.ledger.title"))}]`;

export const LEO_CHAT_STATES: readonly State[] = [
  leo("launcher.closed", (t) => launcher(t), { act: async () => undefined }),
  leo("panel.empty", (t) => exactText(t("leo:agent.emptyTitle")), { scope: "full" }),
  leo("panel.fullscreen", (t) => `button[aria-label=${JSON.stringify(t("leo:agent.collapse"))}]`, {
    viewports: ["desktop"],
    act: async (page, context) => {
      await openPanel(page, context);
      await page.getByRole("button", { name: context.t("leo:agent.fullscreen"), exact: true }).click();
    },
  }),
  leo("chat.populated", () => "div.md-content:has-text(\"Здравствуйте\")", {
    scope: "full",
    storage: chat([question("Привет"), answer("Здравствуйте! Чем помочь с делами на сегодня?")]),
  }),
  leo("chat.markdown", () => ".md-content table", { storage: chat([question("Итоги недели"), answer(MARKDOWN)]) }),
  leo("chat.code", () => "div.md-code span.md-code-lang", { storage: chat([question("Посчитай минуты"), answer(CODE)]) }),
  leo("chat.code-long", () => "pre.md-code-clipped", { storage: chat([question("Список встреч кодом"), answer(LONG_CODE)]) }),
  leo("chat.math", () => "[role=math].md-math", { storage: chat([question("Формула роста"), answer(MATH)]) }),
  leo("chat.mermaid", () => ".md-mermaid svg", { storage: chat([question("Нарисуй процесс"), answer(MERMAID)]) }),
  leo("chat.mermaid-source", (t) => withText("button", t("common:md.diagramView")), {
    storage: chat([question("Нарисуй процесс"), answer(MERMAID)]),
    act: async (page, context) => {
      await openPanel(page, context);
      await page.locator(".md-mermaid svg").waitFor();
      await page.locator(".md-diagram").getByRole("button").first().click();
    },
  }),
  leo("chat.attachments-sent", () => 'text="отчёт.pdf"', {
    storage: chat([question("", { attachments: ["отчёт.pdf"] }), answer("Прочитал отчёт: выручка выросла на 12%.")]),
  }),
  leo("chat.ledger-done", (t) => ledger(t), { storage: withSteps("completed") }),
  leo("chat.ledger-expanded", () => ".leo-ledger-body[data-open=true]", {
    storage: withSteps("completed"),
    act: async (page, context) => {
      await openPanel(page, context);
      await page.locator(ledger(context.t)).getByRole("button").first().click();
    },
  }),
  leo("chat.ledger-failed", (t) => withText(ledger(t), t("leo:agent.ledger.failed")), {
    storage: withSteps("failed", { error: "timeout" }),
  }),
  leo("chat.ledger-cancelled", (t) => ledger(t), { storage: withSteps("cancelled", { error: "rejected" }) }),
];
