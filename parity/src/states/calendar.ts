// Календарь (шаг 4): месяц, неделя, день, загрузка и ошибка, контекстные меню,
// окна события и стрима. Интеграции календаря — calendar-integrations.ts.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { STATUS } from "../ui/draft-ui.ts";
import { alert } from "./common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

const MONTH = "calendar/month";
const EVENTS = "/v1/me/calendar/events";
const menu = "div.pop.fixed";

type Act = NonNullable<State["act"]>;

const dayCell = (t: Translate): string => `button[aria-label=${JSON.stringify(t("calendar:calendar.addOnDay"))}]`;
const event = (title: string): string => `button.cal-ev[aria-label=${JSON.stringify(title)}]`;
const dialog = (title: string): string => `dialog[aria-label=${JSON.stringify(title)}]`;

function calendar(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `calendar.${id}`, fixture: MONTH, scope: "single", marker, ...extra };
}

const view = (key: "week" | "day"): Act => async (page, { t }) => {
  const label = key === "week" ? t("calendar:calendar.nav.week") : t("calendar:calendar.nav.day");
  await page.getByRole("button", { name: label, exact: true }).click();
};

/** Новое событие: выбрать свободный день (23 июля) и «Добавить» в боковой панели. */
async function newEvent(page: Page, { t }: StateContext): Promise<void> {
  await page.locator(dayCell(t)).nth(24).click();
  await page.getByRole("button", { name: t("calendar:calendar.add"), exact: true }).click();
  await page.locator(dialog(t("calendar:calendar.newTitle"))).waitFor();
}

const openEvent = (title: string): Act => async (page) => page.locator(event(title)).first().click();

/** Новое событие с названием — «Сохранить». */
const saveNewEvent: Act = async (page, context) => {
  await newEvent(page, context);
  const form = page.locator(dialog(context.t("calendar:calendar.newTitle")));
  await page.getByLabel(context.t("calendar:calendar.form.title")).fill("Разбор метрик");
  await form.getByRole("button", { name: context.t("common:actions.save"), exact: true }).click();
};

/** Ответ черновика на создание события: форма EventOut (api/me_calendar.py). */
const SAVED_EVENT = {
  id: "5eed0005-0000-4000-8000-000000000001",
  owner_id: "5eed0005-0000-4000-8000-000000000002",
  title: "Разбор метрик",
  description: null,
  start_at: "2026-07-23T07:00:00Z",
  end_at: "2026-07-23T08:00:00Z",
  event_type: "meeting",
  location: null,
  timezone: "Europe/Moscow",
  participants: [],
  reminders: [],
  is_cancelled: false,
  external_source: null,
  recurrence_rule: null,
  parent_event_id: null,
  session_id: null,
  meeting_room_id: null,
  meeting: null,
  created_at: "2026-07-17T12:00:00Z",
  updated_at: null,
};

/** Окно события «Созвон с Acme» → «Удалить»: подтверждение. */
const deleteViaModal: Act = async (page, context) => {
  await openEvent("Созвон с Acme")(page, context);
  await page.locator(dialog(context.t("calendar:calendar.editTitle"))).getByRole("button", { name: context.t("calendar:calendar.delete"), exact: true }).click();
};

/** Прогресс обучения после «Первой встречи» — форма ответа черновика. */
const FIRST_MEETING = {
  status: "completed",
  audio_status: "declined",
  version: 1,
  current_step: null,
  completed_steps: [],
  done_actions: ["first_meeting"],
  started_at: "2026-03-19T12:00:00Z",
  completed_at: "2026-03-19T12:20:00Z",
};

/** Удаление из контекстного меню события: без подтверждения, сразу запрос. */
const deleteFromMenu: Act = async (page, { t }) => {
  await page.locator(event("Созвон с Acme")).first().click({ button: "right" });
  await page.locator(menu).getByRole("button", { name: t("calendar:calendar.delete"), exact: true }).click();
};

export const CALENDAR_STATES: readonly State[] = [
  calendar("month.populated", () => event("Созвон с Acme"), { scope: "full" }),
  // Маркер — сетка месяца: на телефоне боковой панели с «Событий пока нет» нет.
  { id: "calendar.month.empty", fixture: "calendar/empty", scope: "full", marker: (t) => dayCell(t) },
  calendar("loading", () => "main svg.spin", { overrides: [hold("GET", EVENTS)] }),
  calendar("error", (t) => exactText(t("calendar:calendar.loadError")), {
    overrides: [reply("GET", EVENTS, 404, { detail: "Not Found" }, "4xx без повтора: так экран ошибки виден сразу")],
  }),
  calendar("week", () => 'button[aria-label="07:00"]', { scope: "full", act: view("week") }),
  calendar("day", () => 'button[aria-label="07:00"]', { act: view("day") }),
  calendar("context-menu-slot", (t) => withText(menu, t("calendar:calendar.add")), {
    act: async (page, { t }) => page.locator(`button[aria-label=${JSON.stringify(t("calendar:calendar.addOnDay"))}]`).nth(24).click({ button: "right" }),
  }),
  calendar("context-menu-event", (t) => withText(menu, t("calendar:calendar.openEvent")), {
    act: async (page) => page.locator(event("Созвон с Acme")).first().click({ button: "right" }),
  }),
  calendar("event-modal-new", (t) => dialog(t("calendar:calendar.newTitle")), { act: newEvent }),
  calendar("event-modal-video-on", (t) => `button[aria-pressed=true]:has-text(${JSON.stringify(t("calendar:calendar.meeting.toggle"))})`, {
    act: async (page, context) => {
      await newEvent(page, context);
      await page.locator(`button[aria-pressed]:has-text(${JSON.stringify(context.t("calendar:calendar.meeting.toggle"))})`).click();
    },
  }),
  calendar("event-modal-stream-type", (t) => exactText(t("calendar:calendar.type.streamHint")), {
    act: async (page, context) => {
      await newEvent(page, context);
      const form = page.locator(dialog(context.t("calendar:calendar.newTitle")));
      await form.getByRole("combobox").first().click();
      await page.getByRole("option", { name: context.t("calendar:calendar.type.stream") }).click();
    },
  }),
  calendar("event-date-popover", (t) => `input[aria-label=${JSON.stringify(t("calendar:calendar.form.timeStart"))}]`, {
    act: async (page, context) => {
      await newEvent(page, context);
      await page.locator(`button[aria-label=${JSON.stringify(context.t("calendar:calendar.form.date"))}]`).click();
    },
  }),
  calendar("event-modal-validation", (t) => exactText(t("calendar:calendar.err.endBeforeStart")), {
    act: async (page, context) => {
      await newEvent(page, context);
      await page.getByLabel(context.t("calendar:calendar.form.title")).fill("Разбор метрик");
      await page.locator(`button[aria-label=${JSON.stringify(context.t("calendar:calendar.form.date"))}]`).click();
      await page.getByLabel(context.t("calendar:calendar.form.timeEnd")).fill("06:00");
      await page.keyboard.press("Escape");
    },
  }),
  calendar("event-modal-meeting", (t) => exactText(t("calendar:calendar.meeting.join")), { act: openEvent("Созвон с Acme"), reveal: true }),
  calendar("event-modal-stream", (t) => exactText(t("calendar:calendar.stream.openStudio")), { act: openEvent("Эфир: итоги квартала"), reveal: true }),
  calendar("event-modal-session-link", (t) => withText("a", t("calendar:calendar.openRecording")), {
    act: openEvent("Планирование бюджета Q4"),
    reveal: true,
  }),
  calendar("event-delete-confirm", (t) => exactText(t("calendar:calendar.deleteConfirm")), { act: deleteViaModal }),
  calendar("toast-saved", (t) => withText(STATUS, t("calendar:calendar.saved")), {
    overrides: [
      reply("POST", EVENTS, 201, SAVED_EVENT, "новое событие стенд записи не сохраняет: данные засева общие"),
      reply("POST", "/v1/me/onboarding/progress", 200, FIRST_MEETING, "созданное событие отмечает пункт «Первая встреча» чек-листа"),
    ],
    act: saveNewEvent,
  }),
  calendar("toast-save-error", alert((t) => t("calendar:calendar.saveError")), {
    expectsAlert: true,
    overrides: [serverError("POST", EVENTS)],
    act: saveNewEvent,
  }),
  // Тост успеха показывает удаление из окна события; из контекстного меню — только тост отказа.
  calendar("toast-deleted", (t) => withText(STATUS, t("calendar:calendar.deleted")), {
    overrides: [reply("DELETE", `${EVENTS}/{event_id}`, 204, null, "удаление события стенд записи не выполняет: данные засева общие")],
    act: async (page, context) => {
      await deleteViaModal(page, context);
      await page.locator(`dialog[open][aria-label=${JSON.stringify(context.t("calendar:calendar.delete"))}]`)
        .getByRole("button", { name: context.t("calendar:calendar.delete"), exact: true }).click();
    },
  }),
  calendar("toast-delete-error", alert((t) => t("calendar:calendar.deleteError")), {
    expectsAlert: true,
    overrides: [serverError("DELETE", `${EVENTS}/{event_id}`)],
    act: deleteFromMenu,
  }),
  calendar("stream-modal", (t) => dialog(t("streams:stream.list.createTitle")), {
    act: async (page, { t }) => page.getByRole("button", { name: t("calendar:calendar.stream.create"), exact: true }).first().click(),
  }),
];
