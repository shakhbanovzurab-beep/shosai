// Варианты оболочки (шаг 3b): загрузка при старте, экран разрыва связи и его
// снятие, счётчик непрочитанных ответов поддержки.

import type { Page } from "@playwright/test";

import { withText, type Translate } from "../i18n/texts.ts";
import { STATUS } from "../ui/draft-ui.ts";
import { hold, reply } from "./overrides.ts";
import type { Override, State } from "./types.ts";

const HEALTH = "/v1/health";

const connectionDialog = (t: Translate): string => `dialog[aria-label=${JSON.stringify(t("common:connection.title"))}]`;

/** Проба здоровья: первая падает, дальше — заданный ответ. */
function healthProbes(then: "hold" | { status: number; body: { status: string } }, reason: string): Override {
  return { method: "GET", path: HEALTH, respond: ["fail", then], reason };
}

/**
 * Разрыв связи. Сначала оболочка и тишина в сети: слушатель событий сети
 * подписывается при первом рендере, а удачный ответ API во время первой пробы
 * снял бы разрыв и показал тост «Соединение восстановлено».
 */
async function goOffline(page: Page): Promise<void> {
  await page.locator("main").waitFor();
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
}

export const SHELL_VARIANT_STATES: readonly State[] = [
  {
    id: "boot.spinner",
    fixture: "shell/home-free",
    scope: "single",
    overrides: [hold("POST", "/v1/auth/refresh")],
    marker: () => "svg.spin",
  },
  {
    // Разрыв подтверждён первой пробой, вторая висит: «Попытка 1», «Стучимся в
    // сервер…». Анимации сняты (reducedMotion), поэтому пакетов в эфире нет.
    id: "shell.connection-lost",
    fixture: "shell/home-free",
    scope: "full",
    overrides: [healthProbes("hold", "разрыв связи: первая проба падает, вторая остаётся без ответа")],
    act: goOffline,
    marker: (t) =>
      withText(
        withText(connectionDialog(t), t("common:connection.log.noAnswer", { n: 1 })),
        t("common:connection.checking"),
      ),
    mask: {
      // Только отметки времени мм:сс; «Попытка 1» и счёт «Поймано: 0» неподвижны.
      selectors: (t) => [`${connectionDialog(t)} .tnum:text-matches("^\\\\d{2}:\\\\d{2}$")`],
      reason: "журнал разрыва считает секунды по настоящему таймеру, а не по замороженным часам",
    },
  },
  {
    // Сеть вернулась: событие online запускает пробу сразу, она проходит.
    id: "shell.connection-restored",
    fixture: "shell/home-free",
    scope: "single",
    overrides: [healthProbes({ status: 200, body: { status: "ok" } }, "разрыв связи и его конец: первая проба падает, вторая проходит")],
    act: async (page, { t }) => {
      await goOffline(page);
      await page.locator(withText(connectionDialog(t), t("common:connection.log.noAnswer", { n: 1 }))).waitFor();
      await page.evaluate(() => window.dispatchEvent(new Event("online")));
    },
    marker: (t) => withText(STATUS, t("common:connection.restored")),
  },
  {
    id: "shell.support-badge",
    fixture: "shell/home-free",
    scope: "single",
    overrides: [reply("GET", "/v1/me/tickets/unread-count", 200, { count: 3 }, "ответы поддержки приходят от оператора; засев их не создаёт")],
    marker: () => 'a[href="/app/support"]:has-text("3")',
  },
];
