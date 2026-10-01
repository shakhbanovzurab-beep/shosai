// Страница встречи, документ (шаг 4): AI-версия и черновик, сборка AI-версии
// потоком и её отказы, обработка, статусы, приватная встреча, загрузка и 404.
// Конвейера и модели на стенде нет: потоки генерации — синтетика с причиной.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, openStream, reply, serverError, stream, type StreamEvent } from "./overrides.ts";
import type { Override, State, StateContext } from "./types.ts";

const ENHANCE = "/v1/me/sessions/{id}/note/regenerate-enhanced/stream";
const STREAM_REASON = "AI-версию собирает модель, которой на стенде нет";

const fixture = (meeting: string): string => `meetings/detail-${meeting}`;
const docError = (text: (t: Translate) => string) => (t: Translate): string => withText("p.mtg-doc-error", text(t));
const aiTab = (t: Translate): string => `button[aria-label=${JSON.stringify(t("meetings:meet.detail.doc.enhanced"))}]`;

type Act = NonNullable<State["act"]>;

function detail(id: string, meeting: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.detail.${id}`, fixture: fixture(meeting), scope: "single", marker, ...extra };
}

/** Черновик «Синка» → вкладка AI-версии → «Собрать AI-версию». */
async function generate(page: Page, { t }: StateContext): Promise<void> {
  await page.locator(aiTab(t)).click();
  await page.getByRole("button", { name: t("meetings:meet.detail.doc.generateEnhanced"), exact: true }).click();
}

function generation(id: string, override: Override, marker: (t: Translate) => string): State {
  return detail(`enhanced-${id}`, "sync", marker, { overrides: [override], act: generate });
}

/** Готовая AI-версия «Синка», упёршаяся в предел длины: поток с предупреждением. */
const TRUNCATED: readonly StreamEvent[] = [
  { event: "status", data: { phase: "generating" } },
  { event: "delta", data: { text: "## Синк\n" } },
  { event: "warning", data: {} },
  {
    event: "note",
    data: {
      meetingId: "parity-sync",
      draftMarkdown: "",
      enhancedMarkdown: "## Синк\n- Релиз 2.4 — в пятницу.\n- Экспорт отчётов для Acme Дмитрий исправит к среде.\n- Код-ревью — не дольше суток.",
      actionItems: [{ id: "parity-task", text: "Исправить экспорт отчётов для Acme", done: false, sourceSegmentId: null }],
      templateId: null,
      updatedAt: "2026-07-17T12:00:00Z",
      version: 2,
      lastAuthoringClient: "web",
    },
  },
  { event: "done", data: {} },
];

/** Событие отказа генерации — как его шлёт черновик (api/me_notes.py). */
const NO_TRANSCRIPT = { code: "no_transcript", message: "Нет транскрипта или AI недоступен." };

const selectFirstLine: Act = async (page) => {
  await page.locator(".mtg-canvas .cm-line").first().click({ clickCount: 3 });
};

export const MEETINGS_DOC_STATES: readonly State[] = [
  detail("enhanced", "budget", () => "[data-doc-prose]", { scope: "full" }),
  detail("enhanced-menu", "budget", (t) => `.mtg-menu button[aria-label=${JSON.stringify(t("meetings:meet.detail.doc.regenerateAria"))}]`, {
    act: async (page, { t }) => page.locator(`button.mtg-chip[title=${JSON.stringify(t("meetings:meet.detail.doc.enhanced"))}]`).click(),
  }),
  detail("draft", "sync", (t) => `button[aria-label=${JSON.stringify(t("meetings:meet.detail.doc.draft"))}][aria-pressed=true]`, {
    scope: "full",
  }),
  detail("draft-placeholder", "untitled", (t) => exactText(t("meetings:meet.detail.doc.draftPlaceholder"))),
  detail("draft-format-toolbar", "sync", () => "[role=toolbar]", { act: selectFirstLine }),
  detail("enhanced-empty", "sync", (t) => exactText(t("meetings:meet.detail.doc.enhanceHint")), {
    act: async (page, { t }) => page.locator(aiTab(t)).click(),
  }),
  generation("generating", hold("POST", ENHANCE), (t) => exactText(t("meetings:meet.detail.doc.phaseGenerating"))),
  // Текст уже идёт, конца ещё нет: поток открыт.
  generation(
    "streaming",
    openStream("POST", ENHANCE, [
      { event: "status", data: { phase: "generating" } },
      { event: "delta", data: { text: "## Синк\n- Релиз 2.4 — в пятницу.\n- Экспорт отчётов для Acme" } },
    ], STREAM_REASON),
    () => 'article li:has-text("Релиз 2.4")',
  ),
  // 402, 429 и обрыв связи черновик показывает этим же общим текстом — дефект
  // (инвентарь, Findings): в эталон они не входят, v2 показывает свой текст.
  generation("error", serverError("POST", ENHANCE), docError((t) => t("meetings:meet.errors.enhanceFailed"))),
  generation("error-event", stream("POST", ENHANCE, [{ event: "error", data: NO_TRANSCRIPT }], STREAM_REASON),
    docError(() => NO_TRANSCRIPT.message)),
  {
    ...generation("truncated", stream("POST", ENHANCE, TRUNCATED, STREAM_REASON), docError((t) => t("meetings:meet.detail.doc.truncated"))),
    overrides: [
      stream("POST", ENHANCE, TRUNCATED, STREAM_REASON),
      reply("GET", "/v1/me/templates", 200, [], "шаблоны грузит закрытое на снимке меню AI-версии"),
    ],
  },
  detail("enhanced-private", "interview", (t) => exactText(t("meetings:meet.detail.doc.privateNoAi")), {
    act: async (page, { t }) => page.locator(aiTab(t)).click(),
  }),
  detail("private", "interview", (t) => exactText(t("meetings:meet.detail.chip.private")), { scope: "full" }),
  detail("processing", "retro", (t) => exactText(t("meetings:meet.detail.processing.title")), { scope: "full" }),
  detail("status-failed", "demo", (t) => exactText(t("meetings:meet.detail.status.failed"))),
  detail("loading", "budget", () => "svg.spin", { overrides: [hold("GET", "/v1/me/sessions/{id}/full")] }),
  detail("not-found", "budget", (t) => exactText(t("meetings:meet.detail.notFound")), {
    overrides: [reply("GET", "/v1/me/sessions/{id}/full", 404, { detail: "Session not found" }, "чужая или удалённая встреча")],
  }),
  detail("title-rename", "budget", (t) => `input.mtg-doc-title[aria-label=${JSON.stringify(t("meetings:meet.library.renameField"))}]`, {
    act: async (page) => page.locator("button.mtg-doc-title").click(),
  }),
];
