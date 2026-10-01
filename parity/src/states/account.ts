// Состояния оболочки, кабинета, оплаты, обучения, рефералки, загрузок и горячих
// клавиш. Инвентарь: parity/inventory/shell-auth-account-billing.md.

import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { cabinetDialog } from "../ui/draft-ui.ts";
import type { State } from "./types.ts";

const sidebarHome = (t: Translate): string => `[data-sidebar] >> ${exactText(t("common:nav.analytics"))}`;
const downloadBuilds = (): string => "[data-onboarding='download-builds']";

/** Вкладка кабинета; маркер — текст, который есть только на ней. */
function cabinetTab(id: string, fixture: string, text: (t: Translate) => string): State {
  return { id, fixture, scope: "full", marker: (t) => `${cabinetDialog(t)} >> ${withText("*", text(t))}` };
}

export const ACCOUNT_STATES: readonly State[] = [
  // Оболочка: пользователь Free, платный, администратор.
  { id: "shell.user", fixture: "shell/home-free", scope: "full", marker: sidebarHome },
  { id: "shell.paid", fixture: "shell/home-pro", scope: "full", marker: sidebarHome },
  { id: "shell.admin", fixture: "shell/admin", scope: "full", marker: downloadBuilds },
  {
    id: "shell.desktop-rail",
    fixture: "shell/home-free",
    scope: "single",
    act: async (page, { t }) => page.getByRole("button", { name: t("common:actions.collapseMenu") }).click(),
    marker: () => "[data-sidebar='rail']",
  },
  {
    id: "shell.mobile-drawer-open",
    fixture: "shell/home-free",
    scope: "full",
    viewports: ["mobile"],
    act: async (page, { t }) => page.getByRole("button", { name: t("common:menu.open") }).click(),
    marker: (t) => `button[aria-label=${JSON.stringify(t("common:menu.close"))}]`,
  },
  {
    id: "shell.palette.open",
    fixture: "shell/home-free",
    scope: "full",
    viewports: ["desktop"],
    // Кнопкой поиска в боковой панели: тот же путь, что Ctrl+K, но без гонки с
    // подпиской слота на клавиатуру.
    act: async (page) => page.locator("[data-onboarding='sidebar-search']").click(),
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("common:palette.title"))}]`,
  },

  // Кабинет.
  cabinetTab("account.cabinet.general", "account/cabinet-general", (t) => t("account:cab.appearance")),
  {
    id: "account.cabinet.general.lang-menu",
    fixture: "account/cabinet-general",
    scope: "single",
    act: async (page, { t }) =>
      page.locator(cabinetDialog(t)).getByRole("button", { name: t("common:language.label") }).click(),
    marker: (t) => `${cabinetDialog(t)} >> button[aria-pressed=true]:has-text("Русский")`,
  },
  {
    id: "account.cabinet.general.tz-open",
    fixture: "account/cabinet-general",
    scope: "single",
    act: async (page, { t }) =>
      page.locator(cabinetDialog(t)).getByRole("button", { name: t("account:cab.timezone") }).click(),
    marker: () => "[role=listbox]",
  },
  cabinetTab("account.cabinet.profile", "account/cabinet-profile", (t) => t("account:cab.autoSave")),
  {
    id: "account.cabinet.profile.delete-confirm",
    fixture: "account/cabinet-profile",
    scope: "full",
    act: async (page, { t }) =>
      page.locator(cabinetDialog(t)).getByRole("button", { name: t("account:cab.deleteAccountAction") }).click(),
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("account:cab.deleteAccountTitle"))}]`,
  },
  {
    id: "account.cabinet.profile.saved",
    fixture: "account/profile-saved",
    scope: "single",
    act: async (page, { t }) =>
      page.locator(cabinetDialog(t)).getByRole("textbox", { name: t("account:cab.nameLabel") }).fill("Карина Белова-Орлова"),
    marker: (t) => `${cabinetDialog(t)} >> ${withText("*", t("account:cab.saved"))}`,
  },
  cabinetTab("account.cabinet.data", "account/cabinet-data", (t) => t("account:cab.exportTitle")),

  // Оплата: подписка и платежи на разных тарифах.
  cabinetTab("billing.subscription.free", "billing/subscription-free", (t) => t("billing:cab.tariffs")),
  { ...cabinetTab("billing.subscription.exhausted", "billing/subscription-exhausted", (t) => t("billing:cab.limitExhausted")), scope: "single" },
  cabinetTab("billing.subscription.start", "billing/subscription-start", (t) => t("billing:cab.tariffs")),
  cabinetTab("billing.subscription.pro", "billing/subscription-pro", (t) => t("billing:cab.tariffs")),
  cabinetTab("billing.subscription.max", "billing/subscription-max", (t) => t("billing:cab.tariffs")),
  cabinetTab("billing.payments.empty", "billing/payments-free", (t) => t("billing:cab.billing.historyEmpty")),
  { id: "billing.payments.card", fixture: "billing/payments-pro", scope: "full", marker: (t) => `${cabinetDialog(t)} >> text=4242` },

  // Обучение.
  {
    id: "onboarding.welcome",
    fixture: "onboarding/welcome",
    scope: "full",
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("onboarding:welcome.title"))}]`,
  },
  {
    id: "onboarding.tour.step-1",
    fixture: "onboarding/tour-resume",
    scope: "full",
    marker: (t) => withText(".onb-card", t("onboarding:nav.progress", { current: 1, total: 24 })),
  },

  // Разделы.
  { id: "referral.populated", fixture: "referral/populated", scope: "full", marker: (t) => exactText(t("referral:referral.yourLink")) },
  { id: "downloads.populated", fixture: "downloads/populated", scope: "full", marker: downloadBuilds },
  { id: "hotkeys.populated", fixture: "hotkeys/populated", scope: "full", marker: (t) => exactText(t("hotkeys:hotkeys.action.openApp")) },
];
