import type { CardBrand } from "@/lib/card-brand";

import {
  type PayoutStatus,
  type Period,
  PLANS,
  type PlanId,
  type TransactionPaymentMethod,
  type TransactionStatus,
} from "./contract";

export const PLAN_LABELS = Object.fromEntries(PLANS.map((plan) => [plan.id, plan.label])) as Record<PlanId, string>;

export const STATUS_LABELS: Record<TransactionStatus, string> = {
  paid: "Оплачен",
  pending: "В обработке",
  failed: "Ошибка",
  refunded: "Возврат",
};

export const PERIOD_LABELS: Record<Period, string> = {
  "30d": "30 дней",
  "90d": "90 дней",
  "12m": "12 месяцев",
  all: "Всё время",
};

export const PAYOUT_STATUS_LABELS: Record<PayoutStatus, string> = {
  scheduled: "Запланирована",
  in_transit: "В пути",
  paid: "Зачислена",
};

export const CARD_BRAND_LABELS: Record<CardBrand, string> = {
  mir: "Мир",
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "American Express",
  discover: "Discover",
  jcb: "JCB",
  diners: "Diners Club",
  unionpay: "UnionPay",
  unknown: "Карта",
};

/** "Мир •• 4821", "СБП · Т-Банк", "Перевод · Сбербанк" */
export function paymentMethodLabel(method: TransactionPaymentMethod) {
  if (method.type === "card") return `${CARD_BRAND_LABELS[method.brand]} •• ${method.last4}`;
  if (method.type === "sbp") return `СБП · ${method.bank}`;
  return `Перевод · ${method.bank}`;
}
