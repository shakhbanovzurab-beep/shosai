// Страница встречи, панели (шаг 4): майнд-карта, влияние, окно «Поделиться»,
// меню экспорта и действий, папка и хаб встречи.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, openStream, reply, stream } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const FULL = "/v1/me/sessions/{id}/full";
const MINDMAP = "/v1/me/sessions/{id}/regenerate-mindmap/stream";

type Act = NonNullable<State["act"]>;

function panel(id: string, meeting: string, act: Act, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `meetings.detail.${id}`, fixture: `meetings/detail-${meeting}`, scope: "single", act, marker, ...extra };
}

const tab = (key: "mindmap" | "impact") => async (page: Page, { t }: StateContext): Promise<void> => {
  const label = key === "mindmap" ? t("meetings:meet.detail.doc.mindmap") : t("meetings:meet.detail.doc.impact");
  await page.locator(`button[aria-label=${JSON.stringify(label)}]`).click();
};

const openShare: Act = async (page, { t }) => page.locator(`button[title=${JSON.stringify(t("meetings:meet.share.title"))}]`).click();
const shareDialog = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("meetings:meet.share.title"))}]`;
const byLabel = (label: string) => async (page: Page): Promise<void> => page.locator(`button[aria-label=${JSON.stringify(label)}]`).click();

export const MEETINGS_PANEL_STATES: readonly State[] = [
  panel("mindmap-populated", "budget", tab("mindmap"), () => ".mtg-map-node", { scope: "full" }),
  panel("mindmap-loading", "budget", tab("mindmap"), () => "article.mtg-doc--wide svg.spin", {
    overrides: [{ method: "GET", path: FULL, respond: ["recorded", "recorded", "hold"], reason: "третий запрос /full — от вкладки карты" }],
  }),
  panel("mindmap-unavailable", "budget", tab("mindmap"), (t) => exactText(t("meetings:meet.detail.mindmap.unavailable")), {
    overrides: [{ method: "GET", path: FULL, respond: ["recorded", "recorded", { status: 500, body: { error: { code: "internal_error", message: "Internal server error" } } }],
      reason: "третий запрос /full — от вкладки карты — падает; отказ сервера стенд не воспроизводит" }],
  }),
  panel("mindmap-private", "interview", tab("mindmap"), (t) => exactText(t("meetings:meet.detail.mindmap.privateNoMap"))),
  panel("mindmap-empty", "sync", tab("mindmap"), (t) => exactText(t("meetings:meet.detail.mindmap.hint"))),
  panel(
    "mindmap-building",
    "sync",
    async (page, context) => {
      await tab("mindmap")(page, context);
      await page.getByRole("button", { name: context.t("meetings:meet.detail.mindmap.generate"), exact: true }).click();
    },
    (t) => withText("button:disabled", t("meetings:meet.detail.mindmap.generating")),
    { overrides: [hold("POST", MINDMAP)] },
  ),
  panel(
    "mindmap-building-nodes",
    "sync",
    async (page, context) => {
      await tab("mindmap")(page, context);
      await page.getByRole("button", { name: context.t("meetings:meet.detail.mindmap.generate"), exact: true }).click();
    },
    () => '.mtg-map-node:has-text("Экспорт для Acme")',
    {
      overrides: [
        openStream("POST", MINDMAP, [
          { event: "status", data: { phase: "building" } },
          { event: "node", data: { type: "topic", title: "Релиз 2.4", parent_title: null } },
          { event: "node", data: { type: "action_item", title: "Экспорт для Acme", parent_title: "Релиз 2.4" } },
        ], "карту собирает модель, которой на стенде нет; узлы ещё приходят"),
      ],
    },
  ),
  panel(
    "mindmap-failed",
    "sync",
    async (page, context) => {
      await tab("mindmap")(page, context);
      await page.getByRole("button", { name: context.t("meetings:meet.detail.mindmap.generate"), exact: true }).click();
    },
    () => "p.mtg-doc-error",
    { overrides: [stream("POST", MINDMAP, [{ event: "error", data: { code: "generation_failed" } }], "карту собирает модель, которой на стенде нет")] },
  ),
  panel(
    "mindmap-download-menu",
    "budget",
    async (page, context) => {
      await tab("mindmap")(page, context);
      await page.locator(`button[title=${JSON.stringify(context.t("meetings:meet.detail.mindmap.downloadTitle"))}]`).click();
    },
    (t) => exactText(t("meetings:meet.detail.mindmap.png")),
  ),
  panel("impact-populated", "budget", tab("impact"), () => "ul.mtg-impact-list", { scope: "full" }),
  panel("impact-empty", "sync", tab("impact"), (t) => exactText(t("meetings:meet.detail.impact.empty"))),
  panel("impact-loading", "budget", tab("impact"), () => "svg.spin", { overrides: [hold("GET", "/v1/me/sessions/{id}/impact")] }),
  panel(
    "impact-apply-error",
    "budget",
    async (page, context) => {
      await tab("impact")(page, context);
      await page.getByRole("button", { name: context.t("meetings:meet.detail.impact.apply"), exact: true }).first().click();
    },
    () => "p.mtg-impact-error",
    {
      expectsAlert: true,
      overrides: [reply("POST", "/v1/me/sessions/{id}/impact/{impact_id}/apply", 409, { detail: "impact_stale" },
        "изменение уже устарело: задачу поправили, пока встреча обрабатывалась")],
    },
  ),
  panel("share-public", "budget", openShare, (t) => `${shareDialog(t)} input[readonly]`, { scope: "full" }),
  panel("share-private", "sync", openShare, (t) => `${shareDialog(t)} >> ${exactText(t("meetings:meet.share.mode.shared.title"))}`),
  panel("share-password-set", "lawyer", openShare, (t) => exactText(t("meetings:meet.share.passwordSet"))),
  panel("share-loading", "budget", openShare, (t) => `${shareDialog(t)} svg.spin`, { overrides: [hold("GET", "/v1/me/sessions/{id}/share")] }),
  panel("export-menu", "budget", async (page, { t }) => byLabel(t("meetings:meet.export.aria"))(page),
    (t) => exactText(t("meetings:meet.export.downloadFile"))),
  panel("actions-menu-send", "budget", async (page, { t }) => byLabel(t("meetings:meet.detail.actions.menu"))(page),
    () => '.mtg-menu >> text="Slack"'),
  panel("actions-menu", "budget", async (page, { t }) => byLabel(t("meetings:meet.detail.actions.menu"))(page),
    (t) => `[role=switch][aria-label=${JSON.stringify(t("meetings:meet.detail.actions.mcpTitle"))}]`,
    { overrides: [reply("GET", "/v1/me/integrations", 200, [], "платный пользователь без подключённых интеграций")] }),
  panel("folder-menu", "budget",
    async (page, { t }) => page.locator(`button[title=${JSON.stringify(t("meetings:meet.folders.chipTitle", { name: "Финансы" }))}]`).click(),
    (t) => exactText(t("meetings:meet.folders.removeFrom"))),
  panel("folder-menu-unassigned", "sync", async (page, { t }) => page.getByRole("button", { name: t("meetings:meet.folders.addTo"), exact: true }).click(),
    () => '.mtg-menu >> text="Финансы"'),
  panel("hub-popover", "budget", async (page) => page.locator('button:has-text("Acme")').first().click(),
    (t) => `dialog[aria-label=${JSON.stringify(t("hub:hub.meeting.attach"))}]`),
  panel("hub-popover-suggested", "sync", async (page, { t }) => byLabel(t("hub:hub.meeting.looksLike"))(page),
    (t) => `dialog[aria-label=${JSON.stringify(t("hub:hub.meeting.attach"))}]`),
];

