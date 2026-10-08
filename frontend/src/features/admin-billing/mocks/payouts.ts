import type { Currency, Payout, Payouts, Transaction } from "../domain/contract";
import { feeRate, SETTLEMENT } from "./pricing";
import { netMinor } from "./store";
import { DAY, HOUR } from "./types";

const isBusinessDay = (time: number) => {
  const weekday = new Date(time).getUTCDay();
  return weekday !== 0 && weekday !== 6;
};
const startOfDay = (time: number) => time - (time % DAY);
const previousBusinessDay = (day: number) => {
  let previous = day - DAY;
  while (!isBusinessDay(previous)) previous -= DAY;
  return previous;
};

/**
 * Daily settlements of one currency's card (and СБП) payments, net of the provider fee, every business
 * day for the previous one. Bank transfers land in the account directly and are not part of payouts.
 * `transactions` must all be in `currency`.
 */
export function buildPayouts(currency: Currency, transactions: Transaction[], now: number): Payouts {
  const settle = (id: string, from: number, to: number, date: number, status: Payout["status"]): Payout => {
    let gross = 0;
    let fee = 0;
    for (const transaction of transactions) {
      const at = Date.parse(transaction.created_at);
      if (at < from || at >= to || transaction.method.type === "bank_transfer") continue;
      const amount = netMinor(transaction);
      gross += amount;
      fee += Math.round(amount * feeRate(currency, transaction.method.type));
    }
    return { id, date: new Date(date).toISOString(), amount_minor: gross - fee, fee_minor: fee, status };
  };

  const today = startOfDay(now);
  let nextDay = today + DAY;
  while (!isBusinessDay(nextDay)) nextDay += DAY;
  const lastPayoutDay = isBusinessDay(today) ? today : previousBusinessDay(today);
  const next = settle(`po_${currency}_next`, lastPayoutDay, now, nextDay, "scheduled");

  const recent: Payout[] = [];
  let day = lastPayoutDay;
  for (let i = 0; i < 5; i++) {
    const from = previousBusinessDay(day);
    const status = day === today ? "in_transit" : "paid";
    recent.push(settle(`po_${currency}_${day / DAY}`, from, day, day + 10 * HOUR, status));
    day = from;
  }
  return { ...SETTLEMENT[currency], next: next.amount_minor > 0 ? next : null, recent };
}
