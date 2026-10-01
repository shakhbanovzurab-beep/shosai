// Визиты встреч: библиотека, страницы встреч, шаблоны, интеграции и публичная
// страница итога. Состояния — parity/inventory/meetings-calendar-knowledge.md.
//
// Страница встречи часть данных грузит по требованию: окно ссылки, третий запрос
// /full для карты, влияние. Визит открывает их, чтобы ответы попали в фикстуру.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../../i18n/texts.ts";
import { meetingUrl, SEED_IDS, sharedUrl } from "../seed-ids.ts";
import type { Visit, VisitContext } from "./types.ts";

const shareDialog = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("meetings:meet.share.title"))}]`;
const docTab = (label: string): string => `button[aria-label=${JSON.stringify(label)}]`;

/** Окно «Поделиться»: открыть, дождаться ответа, закрыть. */
async function peekShare(page: Page, { t }: VisitContext, inside: string): Promise<void> {
  await page.locator(`button[title=${JSON.stringify(t("meetings:meet.share.title"))}]`).click();
  await page.locator(`${shareDialog(t)} >> ${inside}`).first().waitFor();
  await page.keyboard.press("Escape");
  await page.locator(shareDialog(t)).waitFor({ state: "hidden" });
}

/** Вкладки страницы встречи, которые грузят своё: карта и влияние. */
async function visitTabs(page: Page, { t }: VisitContext, mapMarker: string, impactMarker: string): Promise<void> {
  await page.locator(docTab(t("meetings:meet.detail.doc.mindmap"))).click();
  await page.locator(mapMarker).first().waitFor();
  await page.locator(docTab(t("meetings:meet.detail.doc.impact"))).click();
  await page.locator(impactMarker).first().waitFor();
}

function detail(key: string, marker: (t: Translate) => string, act?: Visit["act"]): Visit {
  return { id: `meetings/detail-${key}`, persona: "lead", url: meetingUrl(key), marker, ...(act === undefined ? {} : { act }) };
}

async function submitPassword(page: Page, { t }: VisitContext, password: string): Promise<void> {
  await page.getByLabel(t("meetings:sharedMeeting.password")).fill(password);
  await page.getByRole("button", { name: t("meetings:sharedMeeting.open") }).click();
}

const libraryCard = (): string => 'a.mtg-card-brand:has-text("Планирование бюджета Q4")';

export const MEETINGS_VISITS: readonly Visit[] = [
  { id: "meetings/library", persona: "lead", url: "/app/meetings", marker: libraryCard },
  { id: "meetings/library-empty", persona: "free", url: "/app/meetings", marker: (t) => exactText(t("meetings:meet.library.emptyTitle")) },
  detail("budget", () => "ul.mtg-impact-list", async (page, context) => {
    await peekShare(page, context, `input[readonly]`);
    await visitTabs(page, context, ".mtg-map-node", "ul.mtg-impact-list");
  }),
  detail("sync", (t) => exactText(t("meetings:meet.detail.impact.empty")), async (page, context) => {
    await page.locator(`${docTab(context.t("meetings:meet.detail.doc.draft"))}[aria-pressed=true]`).waitFor();
    await peekShare(page, context, `text=${JSON.stringify(context.t("meetings:meet.share.mode.shared.title"))}`);
    await visitTabs(page, context, exactText(context.t("meetings:meet.detail.mindmap.hint")), exactText(context.t("meetings:meet.detail.impact.empty")));
  }),
  detail("interview", (t) => exactText(t("meetings:meet.detail.chip.private"))),
  detail("retro", (t) => exactText(t("meetings:meet.detail.processing.title"))),
  detail("demo", (t) => exactText(t("meetings:meet.detail.status.failed"))),
  detail("untitled", (t) => exactText(t("meetings:meet.detail.doc.draftPlaceholder"))),
  detail("lawyer", () => "[data-doc-prose]", async (page, context) => {
    await peekShare(page, context, exactText(context.t("meetings:meet.share.passwordSet")));
  }),
  {
    // Переход по ссылке на реплику: стенограмма открывается сама.
    id: "meetings/detail-deeplink",
    persona: "lead",
    url: `${meetingUrl("budget")}#seg-${SEED_IDS.budgetSegment}`,
    marker: () => `#seg-${SEED_IDS.budgetSegment}`,
  },
  { id: "meetings/templates", persona: "lead", url: "/app/templates", marker: () => 'text="1:1 с руководителем"' },
  { id: "meetings/integrations", persona: "lead", url: "/app/settings/integrations", marker: () => 'text="Whisperer Workspace"' },
  { id: "meetings/integrations-free", persona: "free", url: "/app/settings/integrations", marker: (t) => exactText(t("common:premium.title")) },
  { id: "meetings/shared", persona: null, url: sharedUrl("public"), marker: () => 'h1:has-text("Планирование бюджета Q4")' },
  {
    // Неверный пароль: черновик отвечает {ok:false}, страница остаётся закрытой.
    id: "meetings/shared-locked",
    persona: null,
    url: sharedUrl("locked"),
    marker: (t) => exactText(t("meetings:sharedMeeting.wrong")),
    act: async (page, context) => submitPassword(page, context, "wrong-pass"),
  },
  {
    id: "meetings/shared-unlocked",
    persona: null,
    url: sharedUrl("locked"),
    marker: () => 'h1:has-text("Звонок с юристом по договору")',
    act: async (page, context) => submitPassword(page, context, SEED_IDS.sharePassword),
  },
  { id: "meetings/shared-closed", persona: null, url: sharedUrl("closed"), marker: (t) => exactText(t("meetings:sharedMeeting.commentsClosed")) },
  { id: "meetings/shared-gone", persona: null, url: sharedUrl("expired"), marker: (t) => exactText(t("meetings:sharedMeeting.gone")) },
  {
    // Поиск командного меню по данным «руководителя»: встречи, календарь, контекст, документы.
    id: "meetings/search",
    persona: "lead",
    url: "/app/meetings",
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("common:palette.title"))}] >> text="Планирование бюджета Q4"`,
    act: async (page, { t }) => {
      await page.locator(libraryCard()).waitFor();
      await page.locator("[data-onboarding='sidebar-search']").click();
      await page.locator(`dialog[aria-label=${JSON.stringify(t("common:palette.title"))}] input`).fill("бюджет");
    },
  },
];

