// Съёмка состояний: один тест на состояние, помеченный тегами своих ячеек;
// проект Playwright — это ячейка матрицы, он берёт только свои тесты.
//
// Цель (PARITY_TARGET) — какой фронтенд рисует экран, режим (PARITY_MODE) —
// снять эталон, проверить повторяемость или сравнить v2. Запуск — scripts/parity.sh.

import { expect, test as base } from "@playwright/test";

import { stateSnapshotSegments } from "./baseline/manifest.ts";
import { FIXTURES_DIR, loadParityConfig, ORIGIN } from "./config.ts";
import { installPageSetup, PERSISTENT_ANIMATIONS, RANDOM_SEED } from "./determinism/page-setup.ts";
import { settle } from "./determinism/settle.ts";
import { readFixture } from "./fixtures/format.ts";
import { parseMode, toleranceFor } from "./harness/mode.ts";
import { translator } from "./i18n/texts.ts";
import { cellTag, SINGLE_CELL, type Cell } from "./matrix.ts";
import { FixtureReplay } from "./replay/replay.ts";
import { serveSite } from "./serve/site.ts";
import { thirdPartyStub } from "./serve/third-party.ts";
import { ALL_STATES, stateCells } from "./states/registry.ts";
import { parseTarget, targetSite } from "./targets/target.ts";

const test = base.extend<{ cell: Cell }>({ cell: [SINGLE_CELL, { option: true }] });

const config = loadParityConfig();
const mode = parseMode(process.env["PARITY_MODE"]);
const site = targetSite(parseTarget(process.env["PARITY_TARGET"]), config);

for (const state of ALL_STATES) {
  const tags = stateCells(state).map((cell) => cellTag(cell.name));
  test(state.id, { tag: tags }, async ({ page, context, cell }) => {
    const t = translator(cell.language);
    const fixture = readFixture(FIXTURES_DIR, state.fixture, cell.language);
    const replay = new FixtureReplay(fixture, state.overrides ?? []);
    const storage = { ...fixture.storage, "wh.theme": cell.theme, "wh.lang": cell.language };
    await installPageSetup(context, {
      storage,
      randomSeed: RANDOM_SEED,
      freezeMotion: true,
      persistentAnimations: PERSISTENT_ANIMATIONS,
    });
    await context.routeWebSocket(/\/v1\/ws\//, () => undefined);
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== ORIGIN) {
        const stub = thirdPartyStub(url);
        if (stub === null) return route.abort("blockedbyclient");
        return route.fulfill({ status: 200, contentType: stub.contentType, body: stub.body });
      }
      if (url.pathname.startsWith("/v1/")) return replay.handle(route, url);
      return serveSite(route, url, site);
    });

    await page.clock.setFixedTime(new Date(fixture.clock));
    await page.goto(`${ORIGIN}${state.url ?? fixture.url}`);
    if (state.act !== undefined) await state.act(page, { language: cell.language, t });
    await expect(page.locator(state.marker(t)).first()).toBeVisible();
    if (state.reveal === true) await page.locator(state.marker(t)).first().scrollIntoViewIfNeeded();
    await settle(page, replay);

    expect(replay.unmatched, "запросы без записанного ответа").toEqual([]);
    if (state.expectsAlert !== true) {
      expect(await page.locator("[role=alert]").allInnerTexts(), "неожиданные тосты ошибок").toEqual([]);
    }
    // Указатель — в угол: элементы, следящие за ним (глаза Leo), стоят одинаково.
    // Состояния наведения оставляют его на месте: действие ставит его одинаково.
    if (state.keepPointer !== true) await page.mouse.move(0, 0);
    // Путь по сегментам идентификатора: одной строкой Playwright заменил бы точки
    // на дефисы, и `a.b-c` совпало бы с `a-b.c`.
    await expect(page).toHaveScreenshot(stateSnapshotSegments(state.id), {
      fullPage: true,
      // Движением управляет page-setup: анимации обнулены, тосты стоят. Режим
      // Playwright «disabled» дотянул бы полоску тоста до конца и закрыл его.
      animations: "allow",
      caret: "hide",
      scale: "css",
      mask: (state.mask?.selectors(t) ?? []).map((selector) => page.locator(selector)),
      ...toleranceFor(mode, state),
    });
  });
}
