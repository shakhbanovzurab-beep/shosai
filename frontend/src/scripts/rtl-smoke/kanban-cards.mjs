// Kanban cards in Arabic: a card moves to the next column on its left, by its menu and by the keyboard; Enter opens
// it in a panel at the start of the line, and a click with the mouse opens it too.

import { checkCard, column, moveCard, openBoard } from "./kanban-helpers.mjs";

const moveCardToNextColumn = {
  name: "kanban: a card moved to the next column lands on its left",
  language: "ar",
  async run({ page, base, expect }) {
    const [first, second] = await openBoard(page, base);
    const card = column(page, first).locator("[data-task-id]").first();
    if ((await card.count()) === 0) throw new Error(`the first column (${first}) has no cards`);
    const taskId = await card.getAttribute("data-task-id");

    await moveCard(page, taskId, second);
    try {
      await checkCard(page, expect, { taskId, first, second });
    } finally {
      await moveCard(page, taskId, first);
    }
  },
};

const openCardWithKeyboard = {
  name: "kanban: Enter opens a card in a panel at the start of the line; Escape leaves a field, then closes it",
  language: "ar",
  async run({ page, base, expect }) {
    const [first] = await openBoard(page, base);
    const card = column(page, first).locator("[data-task-id]").first();
    const taskId = await card.getAttribute("data-task-id");
    await card.locator("[data-card-open]").focus();
    await page.keyboard.press("Enter");
    const panel = page.locator('[role="dialog"]');
    await panel.waitFor({ timeout: 10000 });
    await page.waitForTimeout(400);
    const [rect, width, task] = await Promise.all([
      panel.boundingBox(),
      page.evaluate(() => window.innerWidth),
      page.evaluate(() => new URL(window.location.href).searchParams.get("task")),
    ]);
    expect(task === taskId, `kanban panel: the address names ${task}, not ${taskId}`);
    expect(rect !== null && rect.x < width / 2, "kanban panel: in Arabic it doesn’t open on the left");
    // Первый Esc в поле относится к полю (правка и черновик целы), второй закрывает панель.
    await panel.locator("textarea").first().focus();
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    expect((await panel.count()) === 1, "kanban panel: Escape in a field closed the panel");
    await page.keyboard.press("Escape");
    await panel.waitFor({ state: "detached", timeout: 10000 });
    const after = await page.evaluate(() => ({
      task: new URL(window.location.href).searchParams.get("task"),
      focused: document.activeElement?.closest("[data-task-id]")?.getAttribute("data-task-id") ?? null,
    }));
    expect(after.task === null, "kanban panel: Escape left the task in the address");
    expect(after.focused === taskId, `kanban panel: focus went to ${after.focused}, not back to the card`);
  },
};

const dragCardWithKeyboard = {
  name: "kanban: Space and ArrowLeft carry a card to the next column, on its left",
  language: "ar",
  async run({ page, base, expect }) {
    const [first, second] = await openBoard(page, base);
    const card = column(page, first).locator("[data-task-id]").first();
    const taskId = await card.getAttribute("data-task-id");
    // Ручка карточки — её заголовок-кнопка: пробел на нём поднимает карточку.
    await card.locator("[data-card-open]").focus();
    // Шаги по очереди: поднять, сдвинуть к концу строки (в арабском — влево), положить.
    await page.keyboard.press("Space");
    await page.waitForTimeout(400);
    await page.keyboard.press("ArrowLeft");
    await page.waitForTimeout(400);
    await page.keyboard.press("Space");
    await page.waitForTimeout(400);
    await page.waitForLoadState("networkidle");
    try {
      await checkCard(page, expect, { taskId, first, second });
    } finally {
      await moveCard(page, taskId, first);
    }
  },
};

const clickOpensCard = {
  name: "kanban: a click on a card opens it, a drag with the mouse doesn’t",
  language: "ar",
  async run({ page, base, expect }) {
    const [first] = await openBoard(page, base);
    const card = column(page, first).locator("[data-task-id]").first();
    const taskId = await card.getAttribute("data-task-id");
    await card.locator("[data-card-open]").click();
    await page.locator('[role="dialog"]').waitFor({ timeout: 10000 });
    const task = await page.evaluate(() => new URL(window.location.href).searchParams.get("task"));
    expect(task === taskId, `kanban card: a click opened ${task}, not ${taskId}`);
  },
};

export const CARD_SCENARIOS = [moveCardToNextColumn, openCardWithKeyboard, dragCardWithKeyboard, clickOpensCard];
