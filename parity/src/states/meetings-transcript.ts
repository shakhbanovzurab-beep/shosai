// Страница встречи, стенограмма и сводка (шаг 4): панель стенограммы, поиск,
// правка и удаление реплики, переход по ссылке на реплику, говорящие, оглавление.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../i18n/texts.ts";
import type { State, StateContext } from "./types.ts";

type Act = NonNullable<State["act"]>;

const openDock: Act = async (page) => page.locator("button.mtg-dock-pill").click();

function transcript(id: string, meeting: string, act: Act, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.detail.${id}`, fixture: `meetings/detail-${meeting}`, scope: "single", act, marker, ...extra };
}

/** Панель стенограммы открыта; указатель — над первой репликой. */
async function hoverFirst(page: Page, context: StateContext): Promise<void> {
  await openDock(page, context);
  await page.locator(".mtg-seg").first().hover();
}

const guessAccept = (t: Translate): string =>
  `button[aria-label=${JSON.stringify(t("meetings:meet.detail.speakers.guessAccept", { name: "Иван Петров" }))}]`;

export const MEETINGS_TRANSCRIPT_STATES: readonly State[] = [
  // Открытая стенограмма «Бюджета»: второй говорящий предложен как «Иван Петров?».
  transcript("transcript-open", "budget", openDock, guessAccept, { scope: "full" }),
  transcript("transcript-empty", "untitled", openDock, (t) => exactText(t("meetings:meet.detail.transcript.emptyHint"))),
  transcript(
    "transcript-search-match",
    "budget",
    async (page, context) => {
      await openDock(page, context);
      await page.getByLabel(context.t("meetings:meet.detail.transcript.search")).fill("бюджет");
    },
    () => ".mtg-seg[data-match=true]",
  ),
  transcript("transcript-hover-delete", "budget", hoverFirst,
    (t) => `.mtg-seg-drop[title=${JSON.stringify(t("meetings:meet.detail.transcript.deleteSegment"))}]`, { keepPointer: true }),
  transcript(
    "transcript-segment-edit",
    "budget",
    async (page, context) => {
      await openDock(page, context);
      await page.locator("button.mtg-seg-read").first().click();
    },
    (t) => `textarea[aria-label=${JSON.stringify(t("meetings:meet.detail.transcript.editSegment"))}]`,
  ),
  transcript(
    "transcript-delete-confirm",
    "budget",
    async (page, context) => {
      await hoverFirst(page, context);
      await page.locator(`.mtg-seg-drop[title=${JSON.stringify(context.t("meetings:meet.detail.transcript.deleteSegment"))}]`).first().click();
    },
    (t) => `dialog[aria-label=${JSON.stringify(t("meetings:meet.detail.transcript.deleteTitle"))}]`,
  ),
  {
    // Ссылка вида /app/meetings/<id>#seg-<id>: стенограмма открывается сама.
    id: "meetings.detail.transcript-deeplink",
    fixture: "meetings/detail-deeplink",
    scope: "single",
    marker: () => ".mtg-dock-card",
  },
  transcript(
    "speaker-names-modal",
    "budget",
    async (page, context) => {
      await openDock(page, context);
      await page.locator(`[title=${JSON.stringify(context.t("meetings:meet.detail.speakers.renameOne", { name: "Мария Соколова" }))}]`).first().click();
    },
    (t) => `dialog[aria-label=${JSON.stringify(t("meetings:meet.detail.speakers.dialogLabel"))}]`,
  ),
  transcript("aside-outline-expanded", "budget", async (page) => page.locator("button.mtg-aside-kind").first().click(),
    () => "button.mtg-aside-kind[aria-expanded=true]", { viewports: ["desktop"] }),
];
