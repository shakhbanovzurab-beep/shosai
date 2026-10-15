/*
 * Leo's ready-made questions in the admin panel. The admin panel is written in Russian only, so they live
 * here rather than in the message catalogs (see docs/i18n.md).
 */

const ADMIN_DEFAULT = ["Сводка ключевых метрик", "Что изменилось за неделю?", "Найди необычную активность"];

const ADMIN_BY_PREFIX: readonly { prefix: string; suggestions: string[] }[] = [
  {
    prefix: "/admin/dashboard",
    suggestions: ["Сводка ключевых метрик", "Что изменилось за неделю?", "Как идут продажи в CRM?"],
  },
  {
    prefix: "/admin/users",
    suggestions: [
      "Кто зарегистрировался в этом месяце?",
      "Найди неактивных пользователей",
      "Почему аккаунт заблокирован?",
    ],
  },
  {
    prefix: "/admin/plans",
    suggestions: ["Какой тариф популярнее?", "Предложи промокод для Team", "Какие промокоды истекают?"],
  },
  {
    prefix: "/admin/billing",
    suggestions: ["Как изменилась выручка за месяц?", "Покажи неудачные платежи", "Каков отток?"],
  },
  {
    prefix: "/admin/ai-models",
    suggestions: ["На что уходит больше всего денег?", "Спрогнозируй расходы на месяц", "Сравни модели по цене"],
  },
  {
    prefix: "/admin/platform-prompts",
    suggestions: ["Улучши системный промт", "Что изменилось в последней версии?", "Проверь правила безопасности"],
  },
  {
    prefix: "/admin/livekit",
    suggestions: ["Сколько сейчас звонков?", "Есть ли проблемы с качеством связи?", "Нагрузка на узлы"],
  },
  {
    prefix: "/admin/apps",
    suggestions: ["Какая версия сейчас опубликована?", "Подготовь заметки к релизу", "Сколько скачиваний за неделю?"],
  },
  {
    prefix: "/admin/errors",
    suggestions: ["Какие ошибки самые частые?", "Что сломалось после релиза?", "Ошибки на Windows за сутки"],
  },
  {
    prefix: "/admin/support",
    suggestions: ["Какие обращения ждут ответа?", "Предложи ответ клиенту", "Частые темы обращений"],
  },
];

export const isAdminPath = (pathname: string) => pathname === "/admin" || pathname.startsWith("/admin/");

export const adminSuggestions = (pathname: string) =>
  ADMIN_BY_PREFIX.find(({ prefix }) => pathname.startsWith(prefix))?.suggestions ?? ADMIN_DEFAULT;
