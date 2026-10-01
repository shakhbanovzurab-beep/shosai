// Варианты обучения (шаг 3b): шаги тура на маршрутах этой группы, телефонная
// панель под подсветкой, финал, чек-лист и кнопки возврата в обучение.
// Шаги тура на маршрутах других разделов снимаются вместе с теми разделами.

import type { JsonValue } from "../fixtures/format.ts";
import { withText, type Translate } from "../i18n/texts.ts";
import { reply } from "./overrides.ts";
import type { Override, State } from "./types.ts";

const ONBOARDING = "/v1/me/onboarding";
const TOUR_TOTAL = 24;
const REASON = "шаг обучения задаёт прогресс персоны; засев держит каждую персону на одном шаге";

/** Прогресс обучения в форме ответа черновика `GET /v1/me/onboarding`. */
function progress(status: string, step: string | null, done: readonly string[] = [], audio = "declined"): JsonValue {
  return {
    status,
    audio_status: audio,
    version: 1,
    current_step: step,
    completed_steps: [],
    done_actions: [...done],
    started_at: "2026-06-01T12:00:00Z",
    completed_at: status === "completed" ? "2026-07-17T12:00:00Z" : null,
  };
}

/** Тур, продолженный с шага `key`: черновик возвращает на него при входе. */
function resumeAt(key: string): Override[] {
  const body = progress("active", key);
  return [reply("GET", ONBOARDING, 200, body, REASON), reply("POST", `${ONBOARDING}/progress`, 200, body, REASON)];
}

const tourCard = (step: number) => (t: Translate): string =>
  withText(".onb-card", t("onboarding:nav.progress", { current: step, total: TOUR_TOTAL }));

/** Шаг тура на маршруте, чья фикстура даёт данные экрана под подсветкой. */
function tourStep(step: number, key: string, fixture: string): State {
  return { id: `onboarding.tour.step-${step}`, fixture, scope: "single", overrides: resumeAt(key), marker: tourCard(step) };
}

/** Обучение пройдено, из чек-листа сделаны вопрос Leo и загрузка приложения. */
const checklist = reply("GET", ONBOARDING, 200, progress("completed", null, ["first_question", "desktop_downloaded"]), REASON);
const checklistLauncher = (t: Translate): string =>
  `button[aria-label=${JSON.stringify(t("onboarding:launcher.checklist", { done: 2, total: 4 }))}]`;

export const ONBOARDING_VARIANT_STATES: readonly State[] = [
  tourStep(2, "search", "onboarding/tour-resume"),
  tourStep(3, "agent", "onboarding/tour-resume"),
  tourStep(4, "analytics", "onboarding/tour-resume"),
  tourStep(19, "hotkeys", "hotkeys/populated"),
  tourStep(20, "referral", "referral/populated"),
  tourStep(21, "download", "downloads/populated"),
  tourStep(22, "cabinet", "onboarding/tour-resume"),
  // Платные шаги кабинета на Free: вкладки нет, якоря нет — сплошная подложка,
  // карточка по центру и метка «Платный тариф».
  tourStep(23, "leo", "onboarding/tour-resume"),
  tourStep(24, "mcp", "onboarding/tour-resume"),
  {
    // На телефоне якорь в меню: шаг открывает выдвижную панель под подсветкой.
    id: "onboarding.tour.mobile-drawer",
    fixture: "onboarding/tour-resume",
    scope: "single",
    viewports: ["mobile"],
    overrides: resumeAt("search"),
    marker: tourCard(2),
  },
  {
    id: "onboarding.finish",
    fixture: "onboarding/tour-resume",
    scope: "full",
    overrides: [...resumeAt("mcp"), reply("POST", `${ONBOARDING}/complete`, 200, progress("completed", null), REASON)],
    act: async (page, { t }) => page.locator(".onb-card").getByRole("button", { name: t("onboarding:nav.finish") }).click(),
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("onboarding:finish.title"))}]`,
  },
  { id: "onboarding.launcher-checklist", fixture: "shell/home-free", scope: "single", overrides: [checklist], marker: checklistLauncher },
  {
    id: "onboarding.checklist",
    fixture: "shell/home-free",
    scope: "full",
    viewports: ["desktop"],
    overrides: [checklist],
    act: async (page, { t }) => page.locator(checklistLauncher(t)).click(),
    marker: (t) => withText(`dialog[aria-label=${JSON.stringify(t("onboarding:checklist.title"))}]`, t("onboarding:checklist.subtitle")),
  },
  {
    // Голосовой обход не слушали: кнопка в боковой панели зовёт послушать Leo.
    id: "onboarding.launcher-listen",
    fixture: "shell/home-free",
    scope: "single",
    overrides: [reply("GET", ONBOARDING, 200, progress("completed", null, [], "new"), REASON)],
    marker: (t) => `button[aria-label=${JSON.stringify(t("onboarding:welcome.listen", { minutes: 7 }))}]`,
  },
];
