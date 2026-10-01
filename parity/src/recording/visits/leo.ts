// Визиты Leo, промптов, моделей, MCP и хабов. Состояния —
// parity/inventory/leo-prompts-models-mcp-hub.md.
//
// Виджет Leo живёт на любой странице оболочки: его фикстура — домашняя страница
// «руководителя». Переписку, потоки ответа и кадры голоса задаёт состояние.
// Остальные визиты проходят экран так, чтобы в фикстуру попали и вторичные
// запросы: окна памяти, клиенты MCP, скиллы, архив дел и пульс в окне архивации.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../../i18n/texts.ts";
import { cabinetDialog } from "../../ui/draft-ui.ts";
import { hubUrl, mcpConsentUrl, promptUrl } from "../seed-ids.ts";
import type { Visit, VisitContext } from "./types.ts";

const launcher = (t: Translate): string => `button[aria-label=${JSON.stringify(t("leo:agent.open"))}]`;
const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;

async function closeDialog(page: Page, selector: string): Promise<void> {
  await page.keyboard.press("Escape");
  await page.locator(selector).waitFor({ state: "hidden" });
}

/**
 * Вкладка Leo: дождаться блоков, открыть сводку памяти и сохранённые записи.
 * Окна остаются открытыми: Escape во вложенном окне мог закрыть и кабинет.
 */
async function walkLeoCabinet(page: Page, { t }: VisitContext): Promise<void> {
  await page.locator('text="Напомнить: созвон с Acme в 16:00"').waitFor();
  await page.locator('text="olga.kim@example.com"').waitFor();
  await page.getByRole("button", { name: t("leo:leo.memoryManage"), exact: true }).click();
  const summary = dialog(t("leo:leo.memorySummaryTitle"));
  await page.locator(summary).waitFor();
  await page.getByText(t("leo:leo.memoryEntriesLink", { count: 6 }), { exact: true }).click();
  const entries = dialog(t("leo:leo.memoryEntriesTitle"));
  await page.locator(`${entries} >> text="Руководит продуктовым направлением в финтех-компании."`).waitFor();
}

/** Сервер — вкладка по умолчанию; клиенты грузятся при переходе. */
async function walkMcp(page: Page, { t }: VisitContext): Promise<void> {
  await page.locator(exactText(t("mcp:cab.mcp.server.endpoint"))).waitFor();
  await page.getByRole("button", { name: t("mcp:cab.mcp.tab.client"), exact: true }).click();
}

async function walkPrompts(page: Page, { t }: VisitContext): Promise<void> {
  await page.getByRole("button", { name: t("leo:skills.title"), exact: true }).click();
  const skills = dialog(t("leo:skills.title"));
  await page.getByRole("button", { name: t("leo:skills.tabMine", { count: 3 }), exact: true }).click();
  await page.locator(`${skills} >> text="code-review"`).waitFor();
  await closeDialog(page, skills);
}

/** Окно архивации дела: черновик грузит пульс, архив без подтверждения не трогается. */
async function openClosingGate(page: Page, t: Translate, hub: string): Promise<void> {
  await page.locator(`.hub-card:has-text(${JSON.stringify(hub)})`).getByRole("button", { name: t("hub:hub.row.actions"), exact: true }).click();
  await page.getByRole("button", { name: t("hub:hub.row.archive"), exact: true }).click();
  const gate = dialog(t("hub:hub.closing.title", { name: hub }));
  await page.locator(`${gate} >> button:has-text(${JSON.stringify(t("hub:hub.closing.confirm"))})`).waitFor();
  await page.keyboard.press("Escape");
  await page.locator(gate).waitFor({ state: "hidden" });
}

async function walkHubs(page: Page, { t }: VisitContext): Promise<void> {
  await openClosingGate(page, t, "Acme");
  await openClosingGate(page, t, "Северный ветер");
  await page.getByRole("button", { name: t("hub:hub.filter.all"), exact: true }).click();
  await page.locator('text="Ромашка (пилот 2025)"').waitFor();
}

/** Окно материалов: поиск документов и файлов по имени — так черновик ищет без векторного индекса. */
async function pickMaterial(page: Page, { t }: VisitContext): Promise<void> {
  await page.locator(exactText(t("hub:hub.digest.title"))).waitFor();
  await page.getByRole("button", { name: t("hub:hub.materials.add"), exact: true }).click();
  const picker = dialog(t("hub:hub.materials.add"));
  await page.locator(picker).getByLabel(t("hub:hub.materials.searchLabel"), { exact: true }).fill("Бюджет");
  await page.locator(`${picker} >> text="Бюджет 2026.xlsx"`).waitFor();
}

const hubCard = (name: string) => (): string => `.hub-card:has-text(${JSON.stringify(name)})`;

export const LEO_VISITS: readonly Visit[] = [
  { id: "leo/home", persona: "lead", url: "/app/analytics", marker: launcher },
  {
    id: "cabinet/leo",
    persona: "lead",
    url: "/app/cabinet/leo",
    marker: (t) => `${cabinetDialog(t)} >> ${exactText(t("leo:leo.personalizationTitle"))}`,
    act: walkLeoCabinet,
  },
  {
    id: "cabinet/mcp",
    persona: "lead",
    url: "/app/cabinet/mcp",
    marker: (t) => `${cabinetDialog(t)} >> text="Notion MCP"`,
    act: walkMcp,
  },
  { id: "mcp/consent", persona: "lead", url: mcpConsentUrl(), marker: (t) => exactText(t("mcp:cab.mcp.consent.title")) },
  { id: "prompts/list", persona: "lead", url: "/app/prompts", marker: () => 'text="Ответы на звонках продаж"', act: walkPrompts },
  {
    id: "prompts/empty",
    persona: "free",
    url: "/app/prompts",
    marker: (t) => exactText(t("prompts:prompts.empty")),
    act: async (page, { t }) => {
      await page.getByRole("button", { name: t("leo:skills.title"), exact: true }).click();
      await page.getByRole("button", { name: t("leo:skills.tabMine", { count: 0 }), exact: true }).waitFor();
    },
  },
  {
    // Окно скиллов редактора: в фикстуру попадает библиотека (счётчик «Мои»).
    id: "prompts/editor",
    persona: "lead",
    url: promptUrl("coding"),
    marker: () => 'h1:has-text("Собеседование: Python")',
    act: async (page, { t }) => {
      await page.getByRole("button", { name: t("leo:skills.attach"), exact: true }).click();
      await page.getByRole("button", { name: t("leo:skills.tabMine", { count: 3 }), exact: true }).waitFor();
    },
  },
  { id: "prompts/editor-vars", persona: "lead", url: promptUrl("sales"), marker: () => "text=/\\{\\{client\\}\\}/" },
  { id: "models/page", persona: "lead", url: "/app/models", marker: (t) => exactText(t("models:models.rolesTitle")) },
  {
    // Раздел администратора черновик пишет без переводов: тексты одни на всех языках.
    id: "admin/ai-models",
    persona: "admin",
    url: "/app/admin/ai-models",
    marker: () => withText("h1", "Модели и расходы (OpenRouter)"),
  },
  { id: "hub/list", persona: "lead", url: "/app/hub", marker: hubCard("Acme"), act: walkHubs },
  {
    id: "hub/acme",
    persona: "lead",
    url: hubUrl("acme"),
    marker: (t) => exactText(t("hub:hub.digest.title")),
    act: pickMaterial,
  },
  { id: "hub/wind", persona: "lead", url: hubUrl("wind"), marker: (t) => exactText(t("hub:hub.detail.feed")) },
];
