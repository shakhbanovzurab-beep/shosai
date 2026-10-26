/*
 * Leo's words in the admin panel: its ready-made questions and how its panel names the platform. The admin
 * panel is written in Russian only, so they live here rather than in the message catalogs (see docs/i18n.md).
 * The questions are only those the operator's Leo can answer from its `platform` tools (agent step 16):
 * AI spend and its forecast, OpenRouter's balance, plans and promo codes, accounts, and answer ratings.
 */

const ADMIN_DEFAULT = [
  "Сколько потратили на ИИ в этом месяце?",
  "Сколько новых аккаунтов за неделю?",
  "Как оценивают ответы Leo?",
];

const ADMIN_BY_PREFIX: readonly { prefix: string; suggestions: string[] }[] = [
  {
    prefix: "/admin/dashboard",
    suggestions: [
      "Сводка: расходы на ИИ, аккаунты и подписчики",
      "Сколько новых аккаунтов за неделю?",
      "Спрогнозируй расходы на ИИ на месяц",
    ],
  },
  {
    prefix: "/admin/users",
    suggestions: [
      "Сколько аккаунтов зарегистрировалось за 30 дней?",
      "Сколько аккаунтов в каждом доме данных?",
      "Сколько аккаунтов заморожено или ждёт удаления?",
    ],
  },
  {
    prefix: "/admin/plans",
    suggestions: [
      "Сколько подписчиков на каждом тарифе?",
      "Какие промокоды скоро истекут?",
      "Какие промокоды исчерпаны?",
    ],
  },
  {
    prefix: "/admin/ai-models",
    suggestions: [
      "На какие модели уходит больше всего денег?",
      "Спрогнозируй расходы на месяц",
      "Сколько осталось на балансе OpenRouter?",
    ],
  },
];

export const isAdminPath = (pathname: string) => pathname === "/admin" || pathname.startsWith("/admin/");

export const adminSuggestions = (pathname: string) =>
  ADMIN_BY_PREFIX.find(({ prefix }) => pathname.startsWith(prefix))?.suggestions ?? ADMIN_DEFAULT;

/** The platform as Leo's panel names it: the header and what Leo reads there. */
export const PLATFORM_PLACE = {
  label: "Платформа",
  scope:
    "Отвечаю по сводным данным платформы: расходам на ИИ, тарифам и промокодам, аккаунтам и оценкам ответов. " +
    "Ничьих писем, заметок и файлов я здесь не вижу.",
};
