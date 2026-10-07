import type { BillingPeriodScope, PromoStatus } from "./contract";

/** Status names, in the order the status filter lists them. */
export const STATUS_LABEL: Record<PromoStatus, string> = {
  active: "Активен",
  scheduled: "Запланирован",
  expired: "Истёк",
  exhausted: "Исчерпан",
  disabled: "Отключён",
};

export const PERIOD_LABEL: Record<BillingPeriodScope, string> = {
  both: "Месяц и год",
  month: "Месяц",
  year: "Год",
};
