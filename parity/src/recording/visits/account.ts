// Визиты оболочки, кабинета, оплаты, обучения, рефералки, загрузок и горячих
// клавиш. Состояния — parity/inventory/shell-auth-account-billing.md.

import { exactText, withText, type Translate } from "../../i18n/texts.ts";
import { cabinetDialog } from "../../ui/draft-ui.ts";
import type { Visit } from "./types.ts";

/** Вкладка кабинета персоной; маркер — текст, который есть только на этой вкладке. */
function cabinet(id: string, persona: string, tab: string, text: (t: Translate) => string): Visit {
  const url = tab === "" ? "/app/cabinet" : `/app/cabinet/${tab}`;
  return { id, persona, url, marker: (t) => `${cabinetDialog(t)} >> ${withText("*", text(t))}` };
}

const sidebarHome = (t: Translate): string => `[data-sidebar] >> ${exactText(t("common:nav.analytics"))}`;
const downloadBuilds = (): string => "[data-onboarding='download-builds']";

export const ACCOUNT_VISITS: readonly Visit[] = [
  // Оболочка: домашняя страница пользователя и раздел, открытый администратором.
  { id: "shell/home-free", persona: "free", url: "/app/analytics", marker: sidebarHome },
  { id: "shell/home-pro", persona: "pro", url: "/app/analytics", marker: sidebarHome },
  { id: "shell/admin", persona: "admin", url: "/app/download", marker: downloadBuilds },

  // Кабинет: вкладки на тарифе Free.
  cabinet("account/cabinet-general", "free", "", (t) => t("account:cab.appearance")),
  cabinet("account/cabinet-profile", "free", "profile", (t) => t("account:cab.autoSave")),
  cabinet("account/cabinet-data", "free", "data", (t) => t("account:cab.exportTitle")),
  {
    id: "account/profile-saved",
    persona: "editor",
    url: "/app/cabinet/profile",
    marker: (t) => `${cabinetDialog(t)} >> ${withText("*", t("account:cab.saved"))}`,
    mutates: true,
    // Состояние «сохранено» — мелкая вариация вкладки профиля: снимается одной ячейкой.
    languages: ["ru"],
    act: async (page, { t }) => {
      const dialog = page.locator(cabinetDialog(t));
      await dialog.getByRole("textbox", { name: t("account:cab.nameLabel") }).fill("Карина Белова-Орлова");
    },
  },

  // Оплата: подписка и платежи на разных тарифах.
  cabinet("billing/subscription-free", "free", "subscription", (t) => t("billing:cab.tariffs")),
  cabinet("billing/subscription-exhausted", "exhausted", "subscription", (t) => t("billing:cab.limitExhausted")),
  cabinet("billing/subscription-start", "start", "subscription", (t) => t("billing:cab.tariffs")),
  cabinet("billing/subscription-pro", "pro", "subscription", (t) => t("billing:cab.tariffs")),
  cabinet("billing/subscription-max", "max", "subscription", (t) => t("billing:cab.tariffs")),
  cabinet("billing/payments-free", "free", "billing", (t) => t("billing:cab.billing.historyEmpty")),
  {
    id: "billing/payments-pro",
    persona: "pro",
    url: "/app/cabinet/billing",
    marker: (t) => `${cabinetDialog(t)} >> text=4242`,
  },

  // Обучение: приветствие нового пользователя и тур, начатый ранее.
  {
    id: "onboarding/welcome",
    persona: "new",
    url: "/app/analytics",
    marker: (t) => `dialog[aria-label=${JSON.stringify(t("onboarding:welcome.title"))}]`,
  },
  {
    id: "onboarding/tour-resume",
    persona: "tour",
    url: "/app/analytics",
    marker: (t) => withText(".onb-card", t("onboarding:nav.progress", { current: 1, total: 24 })),
  },

  // Разделы с данными персоны.
  { id: "referral/populated", persona: "free", url: "/app/referral", marker: (t) => exactText(t("referral:referral.yourLink")) },
  { id: "downloads/populated", persona: "free", url: "/app/download", marker: downloadBuilds },
  { id: "hotkeys/populated", persona: "free", url: "/app/hotkeys", marker: (t) => exactText(t("hotkeys:hotkeys.action.openApp")) },
  {
    // Любое изменение сочетания черновик не сохраняет: фронтенд шлёт все 22
    // действия, а API принимает не больше 16 (HotkeysUpdate, max_length=16) и
    // отвечает 422 списком ошибок — на экране «Не удалось сохранить». Данные не меняются.
    // Сочетание ⌥⌘J не занято оболочкой: ⌘K во время записи сочетания открыл бы
    // ещё и командное меню (дефект черновика, инвентарь — Findings).
    id: "hotkeys/save-rejected",
    persona: "free",
    url: "/app/hotkeys",
    marker: (t) => exactText(t("hotkeys:hotkeys.saveError")),
    act: async (page) => {
      await page.locator("main button").filter({ hasText: "⌘" }).first().click();
      await page.keyboard.press("Alt+Meta+KeyJ");
    },
  },
];
