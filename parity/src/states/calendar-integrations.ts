// Интеграции календаря (шаг 4): платный барьер, загрузка, подключённый Google,
// ничего не подключено, отключение, ошибка CalDAV, перевыпуск ссылки iCal.

import type { Page } from "@playwright/test";

import { exactText, type Translate } from "../i18n/texts.ts";
import { hold, reply } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const INTEGRATIONS = "/v1/me/calendar/integrations";

/** Список календарей подключённого Google: черновик берёт его у Google вживую. */
const googleCalendars = reply(
  "GET",
  `${INTEGRATIONS}/{integration_id}/calendars`,
  200,
  [
    { id: "maria.sokolova@gmail.com", summary: "Мария Соколова", primary: true, time_zone: "Europe/Moscow" },
    { id: "family.sokolovy@group.calendar.google.com", summary: "Семья", primary: false, time_zone: "Europe/Moscow" },
  ],
  "список календарей черновик запрашивает у Google при открытии окна; стенд в сеть не ходит",
);

const disconnected = reply("GET", INTEGRATIONS, 200, [], "внешний календарь не подключён; при ошибке загрузки окно выглядит так же");

const integrationsDialog = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("calendar:calendar.tab.integrations"))}]`;

async function openIntegrations(page: Page, { t }: StateContext): Promise<void> {
  await page.getByRole("button", { name: t("calendar:calendar.tab.integrations"), exact: true }).first().click();
  await page.locator(integrationsDialog(t)).waitFor();
}

function integrations(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `calendar.integrations-${id}`, fixture: "calendar/month", scope: "single", act: openIntegrations, marker, ...extra };
}

export const CALENDAR_INTEGRATION_STATES: readonly State[] = [
  {
    id: "calendar.integrations-paywall",
    fixture: "calendar/empty",
    scope: "single",
    act: openIntegrations,
    marker: (t) => `${integrationsDialog(t)} >> ${exactText(t("common:premium.title"))}`,
  },
  integrations("connected", (t) => exactText(t("calendar:calendar.integrations.calendars")), { scope: "full", overrides: [googleCalendars] }),
  integrations("loading", (t) => `${integrationsDialog(t)} svg.spin`, { overrides: [hold("GET", INTEGRATIONS)] }),
  integrations("populated", (t) => exactText(t("calendar:calendar.integrations.caldav.url")), { overrides: [disconnected] }),
  integrations("disconnect-confirm", (t) => exactText(t("calendar:calendar.integrations.disconnectConfirm")), {
    overrides: [googleCalendars],
    act: async (page, context) => {
      await openIntegrations(page, context);
      await page.getByRole("button", { name: context.t("calendar:calendar.integrations.disconnect"), exact: true }).click();
    },
  }),
  integrations("caldav-error", (t) => exactText(t("calendar:calendar.integrations.caldav.error")), {
    overrides: [
      disconnected,
      reply("POST", `${INTEGRATIONS}/caldav/connect`, 400, { detail: "caldav_auth_failed" }, "сервер CalDAV отклонил вход; стенд в сеть не ходит"),
    ],
    act: async (page, context) => {
      const { t } = context;
      await openIntegrations(page, context);
      await page.getByLabel(t("calendar:calendar.integrations.caldav.url")).fill("https://caldav.yandex.ru");
      await page.getByLabel(t("calendar:calendar.integrations.caldav.username")).fill("maria@yandex.ru");
      await page.getByLabel(t("calendar:calendar.integrations.caldav.password")).fill("app-password-parity");
      const form = page.getByText(t("calendar:calendar.integrations.provider.caldav")).locator("xpath=ancestor::div[.//button][1]");
      await form.getByRole("button", { name: t("calendar:calendar.integrations.connect"), exact: true }).click();
    },
  }),
  integrations("ical-rotate-confirm", (t) => exactText(t("calendar:calendar.subscription.rotateConfirm")), {
    overrides: [googleCalendars],
    act: async (page, context) => {
      await openIntegrations(page, context);
      await page.getByRole("button", { name: context.t("calendar:calendar.subscription.rotate"), exact: true }).click();
    },
  }),
];

