// Team chats in Arabic: the connect dialog by keyboard and a digest item's "Make a task" in Leo's answer.
// Selectors are data attributes (data-chats-action, data-messenger, data-chat-digest, data-digest-task), never words.

const SETTINGS = "/app/w/lumen/settings";
const HOME = "/app/w/lumen";
const DIGEST_QUESTION = "Go through #release for the week";

const focused = (page) =>
  page.evaluate(() => {
    const element = document.activeElement;
    return {
      inDialog: element?.closest('[role="dialog"]') !== null,
      tag: element?.tagName.toLowerCase() ?? null,
    };
  });

const connectByKeyboard = {
  name: "chats: the connect dialog opens, steps and closes by keyboard, right to left, focus back on its button",
  language: "ar",
  async run({ page, base, expect }) {
    await page.goto(new URL(SETTINGS, base).href, { waitUntil: "networkidle" });
    const connect = page.locator('[data-chats-action="connect"]');
    await connect.waitFor({ timeout: 15000 });
    await connect.focus();
    await page.keyboard.press("Enter");
    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({ timeout: 10000 });
    const direction = await dialog.evaluate((element) => getComputedStyle(element).direction);
    expect(direction === "rtl", `chats connect: the dialog reads ${direction}`);

    // The messenger choice by keyboard; the step that follows takes the focus itself.
    await page.locator('[role="dialog"] [data-messenger="telegram"]').focus();
    await page.keyboard.press("Enter");
    await page.waitForTimeout(500);
    const step = await focused(page);
    expect(step.inDialog && step.tag !== "div", `chats connect: the Telegram step left focus on ${step.tag}`);

    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached", timeout: 10000 });
    // Radix возвращает фокус на следующем такте после закрытия; не вернул — где фокус вместо кнопки.
    const lost = await page
      .waitForFunction(() => document.activeElement?.getAttribute("data-chats-action") === "connect", null, {
        timeout: 3000,
      })
      .then(
        () => null,
        () => page.evaluate(() => document.activeElement?.tagName.toLowerCase() ?? "nothing"),
      );
    expect(lost === null, `chats connect: closing the dialog left focus on ${lost}, not on “Connect a chat”`);
  },
};

const makeTaskFromDigest = {
  name: "chats: a digest item’s “Make a task” sits at the line’s start and keeps focus while it waits for approval",
  language: "ar",
  async run({ page, base, expect }) {
    await page.goto(new URL(HOME, base).href, { waitUntil: "networkidle" });
    await page.locator('[aria-controls="leo-panel"]').click();
    const composer = page.locator("#leo-panel textarea");
    await composer.waitFor({ timeout: 10000 });
    await composer.fill(DIGEST_QUESTION);
    await page.keyboard.press("Enter");
    const card = page.locator("[data-chat-digest]").last();
    const make = card.locator('[data-digest-task="free"]').first();
    await make.waitFor({ timeout: 20000 });

    // In the narrow panel the button goes under the item, at the start of the line — its right side.
    const [button, row] = await Promise.all([make.boundingBox(), make.locator("xpath=..").boundingBox()]);
    expect(
      button !== null && row !== null && row.x + row.width - (button.x + button.width) < 4,
      "chats digest: “Make a task” isn’t at the start (right) of its item",
    );

    await make.focus();
    await page.keyboard.press("Enter");
    await card.locator('[data-digest-task="waiting"]').first().waitFor({ timeout: 10000 });
    const waiting = await page.evaluate(
      () => document.activeElement?.getAttribute("data-digest-task") ?? document.activeElement?.tagName,
    );
    expect(waiting === "waiting", `chats digest: focus went to ${waiting} instead of staying on the item’s button`);
    const cards = await page.locator('#leo-panel [role="group"][id^="leo-proposal-"]').count();
    expect(cards === 1, `chats digest: ${cards} approval cards in the answer instead of one`);
  },
};

export const CHATS_SCENARIOS = [connectByKeyboard, makeTaskFromDigest];
