// Запись фикстур: каждый визит — отдельный тест. Фронтенд черновика работает с
// живым API черновика на стенде записи; всё, что он получил от /v1, после
// нормализации ложится в fixtures/<визит>.json.
//
// Запуск — только через recording/record.sh: он готовит базу, Redis и API.

import path from "node:path";

import { expect, test } from "@playwright/test";

import { loadParityConfig, ORIGIN, PARITY_ROOT } from "../config.ts";
import { installPageSetup } from "../determinism/page-setup.ts";
import { sortExchanges, writeFixture } from "../fixtures/format.ts";
import { serveSite } from "../serve/site.ts";
import { thirdPartyStub } from "../serve/third-party.ts";
import { draftSite } from "../targets/draft.ts";
import { ExchangeJournal } from "./capture.ts";
import { normalizeFixture } from "./normalize.ts";
import { signIn } from "./session.ts";
import { ACCOUNT_VISITS } from "./visits/account.ts";
import { AUTH_VISITS } from "./visits/auth.ts";
import type { Visit } from "./visits/types.ts";

const FIXTURES_DIR = path.join(PARITY_ROOT, "fixtures");
/** Зерно Math.random — то же, что у съёмки: запросы зависят от него так же. */
const RANDOM_SEED = 0x2f6b1d;
const VISITS: readonly Visit[] = [...AUTH_VISITS, ...ACCOUNT_VISITS];

/** Персона изменяющего визита не встречается в других визитах. */
function assertIsolatedMutations(visits: readonly Visit[]): void {
  for (const visit of visits) {
    if (visit.mutates !== true || visit.persona === null) continue;
    const sharing = visits.filter((other) => other !== visit && other.persona === visit.persona);
    if (sharing.length > 0) {
      throw new Error(`Визит ${visit.id} меняет персону ${visit.persona}, её же берут: ${sharing.map((v) => v.id).join(", ")}`);
    }
  }
  const ids = new Set(visits.map((visit) => visit.id));
  if (ids.size !== visits.length) throw new Error("Идентификаторы визитов повторяются");
}

assertIsolatedMutations(VISITS);
const config = loadParityConfig();
const site = draftSite(config);

for (const visit of VISITS) {
  test(visit.id, async ({ page, context }) => {
    const session = visit.persona === null ? null : await signIn(context, visit.persona);
    const storage: Record<string, string> = { "wh.theme": "light", "wh.lang": visit.language ?? "ru" };
    if (session !== null) {
      storage["wh-auth"] = JSON.stringify({ state: { csrfToken: session.csrfToken, user: session.user }, version: 0 });
    }
    await installPageSetup(context, { storage, randomSeed: RANDOM_SEED });

    const journal = new ExchangeJournal(visit.country ?? "RU");
    // Сокеты (/v1/ws/user) открываются без сервера: кадров нет, как у
    // пользователя без событий, и запись от них не зависит.
    await context.routeWebSocket(/\/v1\/ws\//, () => undefined);
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== ORIGIN) {
        const stub = thirdPartyStub(url);
        if (stub === null) return route.abort("blockedbyclient");
        return route.fulfill({ status: 200, contentType: stub.contentType, body: stub.body });
      }
      if (url.pathname.startsWith("/v1/")) return journal.proxy(route, url);
      return serveSite(route, url, site);
    });

    await page.clock.setFixedTime(config.clock);
    await page.goto(`${ORIGIN}${visit.url}`);
    if (visit.act !== undefined) await visit.act(page);
    await expect(page.locator(visit.marker).first()).toBeVisible();
    await journal.waitForQuiet();
    // Тост ошибки, которого визит не ждёт, — признак артефакта стенда (не
    // загрузился сторонний скрипт, не ответил API), а не экрана пользователя.
    if (!visit.marker.includes("[role=alert]")) {
      const alerts = await page.locator("[role=alert]").allInnerTexts();
      expect(alerts, `неожиданные тосты ошибок в визите ${visit.id}`).toEqual([]);
    }

    const fixture = normalizeFixture(
      {
        visit: visit.id,
        persona: visit.persona,
        url: visit.url,
        draftCommit: config.draftCommit,
        clock: config.clock.toISOString(),
        storage,
        exchanges: sortExchanges(journal.exchanges),
      },
      config.clock,
    );
    writeFixture(FIXTURES_DIR, fixture);
  });
}
