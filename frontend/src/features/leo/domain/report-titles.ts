import type { LeoSource } from "./sources";

/*
 * Отчёты платформы как источники ответа оператору (agent шаг 16). Сервер называет их по-английски: заголовок
 * источника читает и модель. Админ-панель только на русском (docs/i18n.md), поэтому здесь отчёт называется
 * по своему id — тем же, что в `platform_reads.py`; незнакомый id показывается с серверным заголовком.
 */

const PERIODS = new Map([
  ["today", "сегодня"],
  ["month", "этот месяц"],
  ["all_time", "всё время"],
]);
const GROUPS = new Map([
  ["provider", "провайдерам"],
  ["model", "моделям"],
  ["feature", "функциям"],
]);

const days = (count: string | undefined) => (count ? `${count} дн.` : null);

const REPORTS = new Map<string, (args: readonly string[]) => string | null>([
  [
    "spend.summary",
    ([period, group]) => {
      const when = PERIODS.get(period ?? "");
      const by = GROUPS.get(group ?? "");
      return when && by ? `Расходы на ИИ, ${when}, по ${by}` : null;
    },
  ],
  ["spend.daily", ([count]) => days(count) && `Расходы на ИИ по дням, ${days(count)}`],
  ["spend.forecast", () => "Прогноз расходов на ИИ на этот месяц"],
  ["openrouter.balance", () => "Баланс OpenRouter"],
  ["ratings", ([count]) => days(count) && `Оценки ответов Leo, ${days(count)}`],
  ["billing.plans", () => "Тарифы и подписчики"],
  ["billing.promo_codes", () => "Промокоды"],
  ["identity.accounts", ([count]) => days(count) && `Аккаунты по домам данных, ${days(count)}`],
]);

/** Название источника в панели: отчёт платформы — по-русски, любой другой — как его назвал сервер. */
export function shownTitle(source: Pick<LeoSource, "kind" | "id" | "title">): string {
  if (source.kind !== "report") return source.title;
  const [name = "", ...args] = source.id.split(":");
  return REPORTS.get(name)?.(args) ?? source.title;
}
