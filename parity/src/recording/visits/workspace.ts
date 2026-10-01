// Визиты календаря, контекста и базы знаний. Состояния —
// parity/inventory/meetings-calendar-knowledge.md.
//
// Календарь грузит события своего вида (месяц, неделя, день — разные from/to),
// окно интеграций — подключения, календари Google и ссылку iCal, окно события —
// список встреч для связи. Визит проходит их все: ответы попадают в фикстуру.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../../i18n/texts.ts";
import { SEED_IDS } from "../seed-ids.ts";
import type { Visit, VisitContext } from "./types.ts";

const acmeCall = (): string => 'button.cal-ev[aria-label="Созвон с Acme"]';
const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;

async function closeDialog(page: Page, selector: string): Promise<void> {
  await page.keyboard.press("Escape");
  await page.locator(selector).waitFor({ state: "hidden" });
}

async function walkCalendar(page: Page, { t }: VisitContext): Promise<void> {
  await page.locator(acmeCall()).waitFor();
  const integrations = dialog(t("calendar:calendar.tab.integrations"));
  await page.getByRole("button", { name: t("calendar:calendar.tab.integrations"), exact: true }).click();
  await page.locator(`${integrations} >> ${exactText(t("calendar:calendar.subscription.title"))}`).waitFor();
  await closeDialog(page, integrations);
  await page.locator(acmeCall()).click();
  const event = dialog(t("calendar:calendar.editTitle"));
  await page.locator(event).waitFor();
  await closeDialog(page, event);
  for (const view of [t("calendar:calendar.nav.week"), t("calendar:calendar.nav.day"), t("calendar:calendar.nav.month")]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await page.locator(`button[aria-pressed=true]:has-text(${JSON.stringify(view)})`).waitFor();
  }
}

const premiumTitle = (t: Translate): string => exactText(t("common:premium.title"));
const documentRow = `#kb-doc-${SEED_IDS.knowledgeDocument}`;

export const WORKSPACE_VISITS: readonly Visit[] = [
  { id: "calendar/month", persona: "lead", url: "/app/calendar", marker: acmeCall, act: walkCalendar },
  { id: "calendar/empty", persona: "free", url: "/app/calendar", marker: (t) => exactText(t("calendar:calendar.empty.title")) },
  { id: "studio/context", persona: "lead", url: "/app/context", marker: (t) => exactText(t("context:context.blockTitle")) },
  { id: "studio/context-free", persona: "free", url: "/app/context", marker: premiumTitle },
  {
    // Файлы — вкладка по умолчанию; источники и каталог грузятся при переходе.
    id: "studio/knowledge",
    persona: "lead",
    url: "/app/knowledge-base",
    marker: () => 'text="Рабочий vault"',
    act: async (page, { t }) => {
      await page.locator(documentRow).waitFor();
      await page.getByRole("button", { name: t("knowledge:kb.tabs.sources"), exact: true }).click();
    },
  },
  {
    id: "studio/knowledge-doc",
    persona: "lead",
    url: `/app/knowledge-base?tab=files&doc=${SEED_IDS.knowledgeDocument}`,
    marker: () => documentRow,
  },
  { id: "studio/knowledge-free", persona: "free", url: "/app/knowledge-base", marker: premiumTitle },
];
