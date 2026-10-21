// Kanban in Arabic: columns read right to left, so "next" is to the left, for the mouse and the keyboard alike.
// Selectors are the board's data attributes (data-column-id, data-task-id, data-menu-action…), never its words.
// Helpers shared by the column and card scenarios.

const KANBAN = "/app/kanban";

export const columnIds = (page) =>
  page.locator("section[data-column-id]").evaluateAll((sections) => sections.map((s) => s.dataset.columnId));
export const column = (page, id) => page.locator(`section[data-column-id="${id}"]`);
export const box = async (page, id) => {
  const rect = await column(page, id).boundingBox();
  if (!rect) throw new Error(`column ${id} isn’t visible`);
  return rect;
};
export const openBoard = async (page, base) => {
  await page.goto(new URL(KANBAN, base).href, { waitUntil: "networkidle" });
  await page.locator("section[data-column-id]").nth(1).waitFor();
  return columnIds(page);
};
export const columnAt = (page, index, id) =>
  page.waitForFunction(
    ([at, expected]) =>
      document.querySelectorAll("section[data-column-id]")[at]?.getAttribute("data-column-id") === expected,
    [index, id],
    { timeout: 10000 },
  );

/** Moves a card to a column through the card's own "⋮" menu: Move to › the column. */
export async function moveCard(page, taskId, toColumn) {
  await page.locator(`[data-task-id="${taskId}"] button[aria-haspopup="menu"]`).click();
  await page.locator('[role="menu"] [data-menu-action="move-to"]').click();
  await page.locator(`[role="menu"] [data-target-column-id="${toColumn}"]`).click();
  await column(page, toColumn).locator(`[data-task-id="${taskId}"]`).waitFor({ timeout: 10000 });
  await page.waitForLoadState("networkidle");
}

/** Picks a column action ("move-earlier", "move-later") from the column's "⋮" menu with the keyboard. */
export async function columnAction(page, columnId, action) {
  await column(page, columnId).locator('[data-column-header] button[aria-haspopup="menu"]').click();
  const item = page.locator(`[role="menu"] [data-menu-action="${action}"]`);
  await item.focus();
  await page.keyboard.press("Enter");
  await page.waitForLoadState("networkidle");
}

/** Moves a column back to the start of the board, one place at a time, after a scenario moved it. */
export async function restoreColumn(page, columnId) {
  for (let step = 0; step < 5; step++) {
    const at = (await columnIds(page)).indexOf(columnId);
    if (at <= 0) return;
    await columnAction(page, columnId, "move-earlier");
    await columnAt(page, at - 1, columnId);
  }
}

export async function checkCard(page, expect, { taskId, first, second }) {
  const [holder, order, from, to, dir] = await Promise.all([
    page
      .locator(`[data-task-id="${taskId}"]`)
      .evaluate((element) => element.closest("section[data-column-id]")?.getAttribute("data-column-id")),
    columnIds(page),
    box(page, first),
    box(page, second),
    page.evaluate(() => document.documentElement.dir),
  ]);
  expect(holder === order[1], `kanban card: it sits in ${holder}, not in the second column ${order[1]}`);
  expect(to.x + to.width <= from.x + 1, "kanban card: the second column isn’t to the left of the first");
  expect(dir === "rtl", `kanban card: <html dir> is ${dir}`);
}
