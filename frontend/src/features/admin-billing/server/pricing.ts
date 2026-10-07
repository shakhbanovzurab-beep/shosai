import type { CardBrand } from "@/lib/card-brand";

import type { Currency, PaidPlanId, TransactionPaymentMethod } from "../domain/contract";
import type { Random } from "./random";

/* Demo price list, payment methods and settlement details, per currency. All amounts in minor units. */

export const PRICES: Record<Currency, { professional: number; team_seat: number; enterprise_step: number }> = {
  RUB: { professional: 149_000, team_seat: 199_000, enterprise_step: 500_000 },
  USD: { professional: 1_500, team_seat: 2_000, enterprise_step: 10_000 },
  EUR: { professional: 1_400, team_seat: 1_800, enterprise_step: 10_000 },
};

/** Who settles card payments in each currency and where the money lands. */
export const SETTLEMENT: Record<Currency, { provider: string; account: string }> = {
  RUB: { provider: "ЮKassa", account: "АО «Т-Банк», р/с •• 4821" },
  USD: { provider: "Stripe", account: "Leo Global Ltd, счёт USD •• 7310" },
  EUR: { provider: "Stripe", account: "Leo Global Ltd, IBAN •• 2954" },
};

/** Provider commission on a settled payment; bank transfers carry none. */
export function feeRate(currency: Currency, method: TransactionPaymentMethod["type"]) {
  if (method === "bank_transfer") return 0;
  if (method === "sbp") return 0.007;
  return currency === "RUB" ? 0.028 : 0.029;
}

export const DECLINES = [
  "Недостаточно средств",
  "Банк отклонил операцию",
  "Истёк срок действия карты",
  "Превышен лимит по карте",
  "Не пройдена проверка 3-D Secure",
];

const SBP_BANKS = ["Сбербанк", "Т-Банк", "Альфа-Банк", "ВТБ", "Озон Банк", "Газпромбанк", "Райффайзенбанк"];
const B2B_BANKS: Record<Currency, string[]> = {
  RUB: ["Сбербанк", "Т-Банк", "Альфа-Банк", "ВТБ", "Точка", "Модульбанк"],
  USD: ["JPMorgan Chase", "Bank of America", "Wise Business"],
  EUR: ["Deutsche Bank", "BNP Paribas", "Revolut Business"],
};

const last4 = (random: Random) => String(random.between(0, 9999)).padStart(4, "0");

/** Enterprise pays invoices by transfer; others pay by card, or by СБП in rubles. */
export function paymentMethod(random: Random, currency: Currency, plan: PaidPlanId): TransactionPaymentMethod {
  if (plan === "enterprise") return { type: "bank_transfer", bank: random.pick(B2B_BANKS[currency]) };
  if (currency !== "RUB") {
    const brand = random.weighted<CardBrand>(
      [
        [0.55, "visa"],
        [0.9, "mastercard"],
      ],
      "amex",
    );
    return { type: "card", brand, last4: last4(random) };
  }
  if (random.chance(0.38)) return { type: "sbp", bank: random.pick(SBP_BANKS) };
  const brand = random.weighted<CardBrand>(
    [
      [0.7, "mir"],
      [0.86, "visa"],
    ],
    "mastercard",
  );
  return { type: "card", brand, last4: last4(random) };
}
