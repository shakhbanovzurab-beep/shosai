// Kanban time in Arabic (ADR 0061): the keyboard starts the stopwatch and sets a timer from the card's panel, and
// the card's time chips read right to left — the icon at the start of the line, on the right.

import { column, openBoard } from "./kanban-helpers.mjs";

/** Focuses the first element matching `selector` and presses Enter, as a keyboard user would. */
async function pressEnterOn(page, selector) {
  const target = page.locator(selector).first();
  await target.waitFor({ timeout: 10000 });
  await target.focus();
  await page.keyboard.press("Enter");
}

const clocksWithKeyboard = {
  name: "kanban: the keyboard starts a stopwatch and sets a timer in the panel; the card's time chips read right to left",
  language: "ar",
  async run({ page, base, expect }) {
    const [first] = await openBoard(page, base);
    const card = column(page, first).locator("[data-task-id]").first();
    await card.locator("[data-card-open]").focus();
    await page.keyboard.press("Enter");
    await page.locator('[role="dialog"]').waitFor({ timeout: 10000 });
    await pressEnterOn(page, '[data-clock-action="start"]');
    await pressEnterOn(page, '[data-clock-action="set-timer"]');
    await pressEnterOn(page, '[data-timer-preset="1800000"]');
    const timer = card.locator('[data-time-chip="timer"]');
    await timer.waitFor({ timeout: 10000 });
    const kinds = await card.locator("[data-time-chip]").evaluateAll((chips) => chips.map((c) => c.dataset.timeChip));
    expect(kinds.includes("stopwatch"), `kanban clocks: the card shows ${kinds.join(", ") || "no"} time chips`);
    const [chip, icon, wide] = await Promise.all([
      timer.boundingBox(),
      timer.locator("svg").first().boundingBox(),
      page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1),
    ]);
    expect(
      chip !== null && icon !== null && icon.x + icon.width / 2 > chip.x + chip.width / 2,
      "kanban clocks: the timer chip's icon isn’t at the start of the line (on the right)",
    );
    expect(!wide, "kanban clocks: the page scrolls sideways with the time chips");
    // Пауза с клавиатуры: на чипе таймера появляется второй значок — пауза.
    await pressEnterOn(page, '[data-clock-action="hold"]');
    const paused = await timer
      .locator("svg")
      .nth(1)
      .waitFor({ timeout: 10000 })
      .then(
        () => true,
        () => false,
      );
    expect(paused, "kanban clocks: Enter on Pause didn’t pause the timer");
  },
};

export const TIME_SCENARIOS = [clocksWithKeyboard];
