import type { Currency, PaidPlanId, Transaction, TransactionPaymentMethod } from "../domain/contract";

export const DAY = 86_400_000;
export const HOUR = 3_600_000;

export type Customer = {
  id: string;
  name: string;
  email: string;
  plan: PaidPlanId;
  seats: number | null;
  /** Prices are set per currency; a customer always pays in the one they signed up in. */
  currency: Currency;
  monthly_minor: number;
  method: TransactionPaymentMethod;
  signup: number;
  churned: number | null;
};

export type RefundEvent = { transaction_id: string; currency: Currency; at: number; amount_minor: number };

export type Store = {
  customers: Customer[];
  /** In creation order, oldest first. */
  transactions: Map<string, Transaction>;
  refunds: RefundEvent[];
};
