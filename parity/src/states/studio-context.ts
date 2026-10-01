// Контекст о себе (шаг 4): платный барьер, загрузка, заполненный и пустой,
// сохранение, загрузка файлов и отказ по размеру.

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { ALERT } from "../ui/draft-ui.ts";
import { hold, reply } from "./overrides.ts";
import type { State } from "./types.ts";

const CONTEXT = "/v1/admin/context";
const MIB = 1024 * 1024;
/** Подстановка, которую фронтенд форматирует сам (размер): маркер — текст до неё. */
const SLOT = "\u0000";

function context(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `context.${id}`, fixture: "studio/context", scope: "single", marker, ...extra };
}

const uploadInput = (t: Translate): string => `input[aria-label=${JSON.stringify(t("context:context.uploadFiles"))}]`;

export const STUDIO_CONTEXT_STATES: readonly State[] = [
  context("populated", (t) => exactText(t("context:context.blockTitle")), { scope: "full" }),
  { id: "context.paywall", fixture: "studio/context-free", scope: "full", marker: (t) => exactText(t("common:premium.title")) },
  context("loading", () => "main svg.spin", { overrides: [hold("GET", CONTEXT)] }),
  context("empty", (t) => exactText(t("context:context.filesEmpty")), {
    overrides: [reply("GET", CONTEXT, 200, { id: "5eed0004-0000-4000-8000-000000000001", text: "", roles: [], updated_at: null, files: [] },
      "контекст ещё не заполнен; при ошибке загрузки экран выглядит так же")],
  }),
  context("saving", (t) => exactText(t("context:context.saving")), {
    overrides: [hold("PUT", CONTEXT)],
    act: async (page) => {
      await page.locator("textarea[data-onboarding='context-editor']").click();
      await page.keyboard.press("Control+End");
      await page.keyboard.type(" Спасибо.");
    },
  }),
  context("uploading", () => "main svg.spin", {
    overrides: [hold("POST", `${CONTEXT}/files`)],
    act: async (page, { t }) =>
      page.locator(uploadInput(t)).setInputFiles({ name: "заметки.md", mimeType: "text/markdown", buffer: Buffer.from("# Заметки\n") }),
  }),
  context("too-large-toast", (t) => withText(ALERT, t("context:context.tooLarge", { size: SLOT }).split(SLOT)[0] ?? ""), {
    expectsAlert: true,
    act: async (page, { t }) =>
      page.locator(uploadInput(t)).setInputFiles({ name: "архив.pdf", mimeType: "application/pdf", buffer: Buffer.alloc(6 * MIB, 1) }),
  }),
];
