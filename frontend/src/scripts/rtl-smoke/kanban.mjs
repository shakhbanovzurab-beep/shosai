// Kanban in Arabic: columns read right to left, so "next" is to the left, for the mouse and the keyboard alike.
// Selectors are the board's data attributes (data-column-id, data-task-id, data-menu-action…), never its words.
// Each scenario puts the demo board back the way it found it.

import { CARD_SCENARIOS } from "./kanban-cards.mjs";
import { box, column, columnAction, columnAt, columnIds, openBoard, restoreColumn } from "./kanban-helpers.mjs";
import { TIME_SCENARIOS } from "./kanban-time.mjs";

const moveColumnWithKeyboard = {
  name: "kanban: the keyboard moves a column towards the left",
  language: "ar",
  async run({ page, base, expect }) {
    const [first] = await openBoard(page, base);
    try {
      await moveColumn(page, expect, first);
    } finally {
      await restoreColumn(page, first);
    }
  },
};

async function moveColumn(page, expect, first) {
  const start = await box(page, first);

  // The column menu's "move later" (towards the end of the line), chosen with Enter.
  await columnAction(page, first, "move-later");
  await columnAt(page, 1, first);
  const afterMenu = await box(page, first);
  expect(afterMenu.x < start.x - 1, "kanban column: “move later” didn’t move it to the left");

  // Dragging with the keyboard: Space picks the column up, ArrowLeft heads for the end in Arabic.
  await column(page, first).locator("[data-column-handle]").focus();
  await page.keyboard.press("Space");
  await page.waitForTimeout(300);
  await page.keyboard.press("ArrowLeft");
  await page.waitForTimeout(600);
  await page.keyboard.press("Space");
  await columnAt(page, 2, first);
  await page.waitForLoadState("networkidle");
  const afterDrag = await box(page, first);
  expect(afterDrag.x < afterMenu.x - 1, "kanban column: ArrowLeft while dragging didn’t move it to the left");
}

const dragColumnWithMouse = {
  name: "kanban: the mouse drags a column by its handle towards the left",
  language: "ar",
  async run({ page, base, expect }) {
    const [first, second] = await openBoard(page, base);
    try {
      const handle = await column(page, first).locator("[data-column-handle]").boundingBox();
      const to = await box(page, second);
      if (!handle) throw new Error("the first column has no handle");
      await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
      await page.mouse.down();
      // Шагами, как живая рука: через середину второй колонки к её левому краю.
      await page.mouse.move(to.x + to.width / 2, handle.y + 20, { steps: 10 });
      await page.mouse.move(to.x + 20, handle.y + 20, { steps: 10 });
      await page.mouse.up();
      await columnAt(page, 1, first);
      const order = await columnIds(page);
      expect(order[1] === first, `kanban column: after the mouse drag ${order[1]} is second, not ${first}`);
    } finally {
      await restoreColumn(page, first);
    }
  },
};

export const KANBAN_SCENARIOS = [moveColumnWithKeyboard, dragColumnWithMouse, ...CARD_SCENARIOS, ...TIME_SCENARIOS];
