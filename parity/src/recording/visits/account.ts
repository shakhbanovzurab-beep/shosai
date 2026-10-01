// Визиты оболочки, кабинета, оплаты, обучения, рефералки, загрузок и горячих
// клавиш. Состояния — parity/inventory/shell-auth-account-billing.md.

import type { Visit } from "./types.ts";

const CABINET = "dialog[aria-label='Личный кабинет']";

/** Вкладка кабинета персоной; маркер — текст, который есть только на этой вкладке. */
function cabinet(id: string, persona: string, tab: string, text: string): Visit {
  const url = tab === "" ? "/app/cabinet" : `/app/cabinet/${tab}`;
  return { id, persona, url, marker: `${CABINET} >> text=${text}` };
}

export const ACCOUNT_VISITS: readonly Visit[] = [
  // Оболочка: домашняя страница пользователя и раздел, открытый администратором.
  { id: "shell/home-free", persona: "free", url: "/app/analytics", marker: "[data-sidebar] >> text=Активность" },
  { id: "shell/home-pro", persona: "pro", url: "/app/analytics", marker: "[data-sidebar] >> text=Активность" },
  { id: "shell/admin", persona: "admin", url: "/app/download", marker: "[data-onboarding='download-builds']" },

  // Кабинет: вкладки на тарифе Free.
  cabinet("account/cabinet-general", "free", "", "Внешний вид"),
  cabinet("account/cabinet-profile", "free", "profile", "Изменения сохраняются автоматически"),
  cabinet("account/cabinet-data", "free", "data", "Экспорт данных"),
  {
    id: "account/profile-saved",
    persona: "editor",
    url: "/app/cabinet/profile",
    marker: `${CABINET} >> text=Изменения сохранены`,
    mutates: true,
    act: async (page) => {
      const dialog = page.getByRole("dialog", { name: "Личный кабинет" });
      await dialog.getByRole("textbox", { name: "Имя" }).fill("Карина Белова-Орлова");
    },
  },

  // Оплата: подписка и платежи на разных тарифах.
  cabinet("billing/subscription-free", "free", "subscription", "Тарифы"),
  cabinet("billing/subscription-exhausted", "exhausted", "subscription", "Лимит исчерпан"),
  cabinet("billing/subscription-start", "start", "subscription", "Тарифы"),
  cabinet("billing/subscription-pro", "pro", "subscription", "Тарифы"),
  cabinet("billing/subscription-max", "max", "subscription", "Тарифы"),
  cabinet("billing/payments-free", "free", "billing", "Платежей пока нет"),
  cabinet("billing/payments-pro", "pro", "billing", "4242"),

  // Обучение: приветствие нового пользователя и тур, начатый ранее.
  { id: "onboarding/welcome", persona: "new", url: "/app/analytics", marker: "dialog[aria-label='Добро пожаловать в Whisperer']" },
  { id: "onboarding/tour-resume", persona: "tour", url: "/app/analytics", marker: ".onb-card >> text=Шаг 1 из 24" },

  // Разделы без данных персоны и с ними.
  { id: "referral/populated", persona: "free", url: "/app/referral", marker: "text=Ваша реферальная ссылка" },
  { id: "downloads/populated", persona: "free", url: "/app/download", marker: "[data-onboarding='download-builds']" },
  { id: "hotkeys/populated", persona: "free", url: "/app/hotkeys", marker: "text=Открыть приложение" },
];
