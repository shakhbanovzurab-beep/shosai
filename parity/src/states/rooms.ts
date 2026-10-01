// Видеокомната ведущего (шаг 6): вход (нужен вход, загрузка, встреча завершена,
// ошибка), предпросмотр камеры и комната, в которой медиасервер не ответил.
//
// Медиасервера у стенда нет: сокет LiveKit закрывается, и комната остаётся в
// «не удалось подключиться» — док, панели и меню рисуются по HTTP. Плитки
// участников, доска и живые субтитры требуют SFU и вне матрицы (решение 3 D2).
// Панели переводчика, AI-ассистента и запись — rooms-panels.ts.

import type { Page } from "@playwright/test";

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { hold, serverError } from "./overrides.ts";
import type { State, StateContext } from "./types.ts";

export const TOKEN = "/v1/me/rooms/{id}/token";

export const connectError = (t: Translate): string => exactText(t("rooms:rooms.connectError"));
/** Кнопка дока по её подписи. */
export const dock = (label: string): string => `.vroom-dock button[aria-label=${JSON.stringify(label)}]`;
/** Боковая панель комнаты с заголовком. */
export const panel = (title: string): string => withText(".vroom-panel", title);

/** Камера предпросмотра — поддельное устройство Chromium: кадр с бегущим счётчиком. */
export const CAMERA_MASK = {
  selectors: () => ["video"],
  reason: "поддельная камера Chromium рисует движущийся кадр со счётчиком; v2 показывает тот же поток",
} as const;

/** Войти из предпросмотра: кнопка с тем же текстом, что заголовок. */
export async function join(page: Page, { t }: StateContext): Promise<void> {
  await page.getByRole("button", { name: t("rooms:meeting.prejoin.join"), exact: true }).click();
  await page.locator(connectError(t)).first().waitFor();
}

export async function openMore(page: Page, context: StateContext): Promise<void> {
  await join(page, context);
  await page.locator(dock(context.t("rooms:meeting.ctl.more"))).click();
}

/** Пункт меню «Ещё»: доска, переводчик, AI-ассистент. */
export const moreItem = (item: (t: Translate) => string) => async (page: Page, context: StateContext): Promise<void> => {
  await openMore(page, context);
  await page.locator("div.pop").getByRole("button", { name: item(context.t), exact: true }).click();
};

const dockButton = (label: (t: Translate) => string) => async (page: Page, context: StateContext): Promise<void> => {
  await join(page, context);
  await page.locator(dock(label(context.t))).click();
};

function host(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `rooms.${id}`, fixture: "rooms/host", scope: "single", marker, ...extra };
}

export const ROOMS_STATES: readonly State[] = [
  { id: "rooms.host.signin-required", fixture: "rooms/host-anonymous", scope: "full", marker: (t) => exactText(t("rooms:rooms.signInTitle")) },
  host("host.loading", () => "div.fixed.inset-0 svg.spin", { overrides: [hold("POST", TOKEN)] }),
  { id: "rooms.host.finished", fixture: "rooms/host-closed", scope: "single", marker: (t) => exactText(t("rooms:rooms.finishedTitle")) },
  host("host.error", (t) => exactText(t("rooms:rooms.errorTitle")), { overrides: [serverError("POST", TOKEN)] }),

  host("prejoin.granted", () => "[role=combobox]", {
    scope: "full",
    mask: CAMERA_MASK,
  }),
  host("prejoin.denied", (t) => exactText(t("rooms:meeting.prejoin.denied")), { mediaAccess: "denied" }),
  host("prejoin.permission-pending", (t) => exactText(t("rooms:meeting.prejoin.camOn")), { mediaAccess: "pending" }),
  host("prejoin.cam-off", (t) => exactText(t("rooms:meeting.prejoin.camOff")), {
    act: async (page, { t }) => page.getByRole("button", { name: t("rooms:meeting.prejoin.camOn"), exact: true }).click(),
  }),

  host("room.connect-error", connectError, { scope: "full", act: join }),
  host("room.connecting", (t) => dock(t("rooms:meeting.ctl.leave")), {
    sockets: [{ path: "/rtc/v1", frames: [], reason: "медиасервер принял соединение и ещё не ответил" }],
    act: async (page, { t }) => page.getByRole("button", { name: t("rooms:meeting.prejoin.join"), exact: true }).click(),
  }),
  { id: "rooms.room.e2ee", fixture: "rooms/host-e2ee", scope: "single", marker: connectError, act: join },
  host("room.chat.empty", (t) => withText(panel(t("rooms:meeting.chat.title")), t("rooms:meeting.chat.empty")), {
    act: dockButton((t) => t("rooms:meeting.chat.title")),
  }),
  host("room.reactions-picker", (t) => `.vroom-pop button[aria-label=${JSON.stringify(`${t("rooms:meeting.reactions.title")}: 👍`)}]`, {
    act: dockButton((t) => t("rooms:meeting.reactions.title")),
  }),
  host("room.invite-modal", (t) => withText(`[aria-label=${JSON.stringify(t("rooms:meeting.invite.title"))}]`, t("rooms:meeting.invite.hint")), {
    act: dockButton((t) => t("rooms:meeting.invite.title")),
  }),
  host("room.more-menu", (t) => withText("div.pop", t("rooms:meeting.ai.title")), { act: openMore }),
  {
    id: "rooms.room.more-menu.e2ee",
    fixture: "rooms/host-e2ee",
    scope: "single",
    marker: (t) => withText("div.pop", t("rooms:meeting.translator.title")),
    act: openMore,
  },
  host("room.more-menu.mobile", (t) => withText("div.pop", t("rooms:meeting.invite.title")), {
    scope: "full",
    viewports: ["mobile"],
    act: openMore,
  }),
];
