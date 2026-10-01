// Запись фикстур: каждый визит на каждом своём языке — отдельный тест. Фронтенд
// черновика работает с живым API черновика на стенде записи; всё, что он получил
// от /v1, после нормализации ложится в fixtures/<визит>.<язык>.json.
//
// Запуск — только через recording/record.sh: он готовит базу, Redis и API.

import { expect, test } from "@playwright/test";

import { FIXTURES_DIR, loadParityConfig, ORIGIN } from "../config.ts";
import { installPageSetup, RANDOM_SEED } from "../determinism/page-setup.ts";
import { sortExchanges, writeFixture } from "../fixtures/format.ts";
import { translator } from "../i18n/texts.ts";
import { browserLocale } from "../matrix.ts";
import { serveSite } from "../serve/site.ts";
import { thirdPartyStub } from "../serve/third-party.ts";
import { draftSite } from "../targets/draft.ts";
import { ExchangeJournal } from "./capture.ts";
import { normalizeFixture } from "./normalize.ts";
import { signIn } from "./session.ts";
import { ACCOUNT_VISITS } from "./visits/account.ts";
import { ADMIN_VISITS } from "./visits/admin.ts";
import { ADMIN_OPS_VISITS } from "./visits/admin-ops.ts";
import { AUTH_VISITS } from "./visits/auth.ts";
import { FILES_VISITS } from "./visits/files.ts";
import { MEETINGS_VISITS } from "./visits/meetings.ts";
import { ROOMS_VISITS } from "./visits/rooms.ts";
import { LEO_VISITS } from "./visits/leo.ts";
import { DEFAULT_LANGUAGES, type Visit } from "./visits/types.ts";
import { WORKSPACE_VISITS } from "./visits/workspace.ts";

const VISITS: readonly Visit[] = [...AUTH_VISITS, ...ACCOUNT_VISITS, ...MEETINGS_VISITS, ...WORKSPACE_VISITS, ...LEO_VISITS, ...ROOMS_VISITS, ...FILES_VISITS, ...ADMIN_VISITS, ...ADMIN_OPS_VISITS];

/** Персона изменяющего визита не встречается в других визитах; id уникальны. */
function assertConsistentVisits(visits: readonly Visit[]): void {
  for (const visit of visits) {
    if (visit.mutates !== true || visit.persona === null) continue;
    const sharing = visits.filter((other) => other !== visit && other.persona === visit.persona);
    if (sharing.length > 0) {
      throw new Error(`Визит ${visit.id} меняет персону ${visit.persona}, её же берут: ${sharing.map((v) => v.id).join(", ")}`);
    }
  }
  if (new Set(visits.map((visit) => visit.id)).size !== visits.length) throw new Error("Идентификаторы визитов повторяются");
}

assertConsistentVisits(VISITS);
const config = loadParityConfig();
const site = draftSite(config);
const languages = [...new Set(VISITS.flatMap((visit) => visit.languages ?? DEFAULT_LANGUAGES))].sort();

for (const language of languages) {
  test.describe(language, () => {
    test.use({ locale: browserLocale(language) });
    const t = translator(language);

    for (const visit of VISITS.filter((v) => (v.languages ?? DEFAULT_LANGUAGES).includes(language))) {
      test(`${visit.id}.${language}`, async ({ page, context }) => {
        const session = visit.persona === null ? null : await signIn(context, visit.persona);
        const storage: Record<string, string> = { "wh.theme": "light", "wh.lang": language, ...visit.storage };
        if (session !== null) {
          const user = { ...session.user, language };
          storage["wh-auth"] = JSON.stringify({ state: { csrfToken: session.csrfToken, user }, version: 0 });
        }
        await installPageSetup(context, {
          storage,
          ...(visit.session === undefined ? {} : { session: visit.session }),
          randomSeed: RANDOM_SEED,
          freezeMotion: false,
          persistentAnimations: [],
          entryAnimations: [],
        });

        const journal = new ExchangeJournal(visit.country ?? "RU", language);
        // Сокеты своего API (/v1/ws/user) открываются без сервера: кадров нет,
        // как у пользователя без событий, и запись от них не зависит. Сокеты на
        // чужие хосты (медиасервер из ответа на вход в комнату) закрываются: в
        // сеть запись не ходит.
        await context.routeWebSocket(/.*/, (socket) => {
          if (!new URL(socket.url()).pathname.startsWith("/v1/")) void socket.close();
        });
        await context.route("**/*", async (route) => {
          const url = new URL(route.request().url());
          if (url.origin !== ORIGIN) {
            const stub = thirdPartyStub(url);
            if (stub === null) return route.abort("blockedbyclient");
            return route.fulfill({ status: 200, contentType: stub.contentType, body: stub.body });
          }
          const call = `${route.request().method()} ${url.pathname}`;
          if ((visit.hold ?? []).includes(call)) return undefined;
          const stub = visit.stubs?.find((candidate) => `${candidate.method} ${candidate.path}` === call);
          if (stub !== undefined) return journal.stub(route, url, stub);
          if (url.pathname.startsWith("/v1/")) return journal.proxy(route, url);
          return serveSite(route, url, site);
        });

        await page.clock.setFixedTime(config.clock);
        await page.goto(`${ORIGIN}${visit.url}`);
        if (visit.act !== undefined) await visit.act(page, { language, t });
        const marker = visit.marker(t);
        await expect(page.locator(marker).first()).toBeVisible();
        await journal.waitForQuiet();
        // Тост ошибки, которого визит не ждёт, — признак артефакта стенда (не
        // загрузился сторонний скрипт, не ответил API), а не экрана пользователя.
        if (!marker.includes("[role=alert]")) {
          const alerts = await page.locator("[role=alert]").allInnerTexts();
          expect(alerts, `неожиданные тосты ошибок в визите ${visit.id}`).toEqual([]);
        }

        const fixture = normalizeFixture(
          {
            visit: visit.id,
            language,
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
  });
}
