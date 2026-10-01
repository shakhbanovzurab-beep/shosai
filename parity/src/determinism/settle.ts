// Ожидание «экран готов к снимку»: шрифты загружены, API и DOM молчат.
//
// Пилот показал, что одного document.fonts.ready мало: часть подмножеств
// шрифта запрашивается позже, когда на экране появляются их символы, и снимок
// выходил то со старым, то с новым начертанием. Поэтому ждём ещё и тишины.

import type { Page } from "@playwright/test";

import type { FixtureReplay } from "../replay/replay.ts";

const QUIET_MS = 500;
const SETTLE_DEADLINE_MS = 20_000;
const POLL_MS = 100;

interface PageQuiet {
  readonly fontsLoaded: boolean;
  readonly domQuietFor: number;
}

export async function settle(page: Page, replay: FixtureReplay): Promise<void> {
  const deadline = Date.now() + SETTLE_DEADLINE_MS;
  for (;;) {
    const state = await page.evaluate(async (): Promise<PageQuiet> => {
      await document.fonts.ready;
      const tracker = window as unknown as { __parityLastMutation?: number };
      return {
        fontsLoaded: document.fonts.status === "loaded",
        domQuietFor: performance.now() - (tracker.__parityLastMutation ?? 0),
      };
    });
    if (state.fontsLoaded && state.domQuietFor >= QUIET_MS && replay.quietFor >= QUIET_MS) return;
    if (Date.now() > deadline) {
      throw new Error(
        `Экран не успокоился за ${SETTLE_DEADLINE_MS} мс: шрифты ${state.fontsLoaded ? "готовы" : "грузятся"}, ` +
          `DOM молчит ${Math.round(state.domQuietFor)} мс, API — ${replay.quietFor} мс`,
      );
    }
    await page.waitForTimeout(POLL_MS);
  }
}
