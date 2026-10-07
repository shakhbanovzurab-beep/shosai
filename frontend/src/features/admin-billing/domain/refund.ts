import type { Transaction } from "./contract";

/** What is left to refund, in the transaction's currency; only settled payments can be refunded. */
export const refundableMinor = (transaction: Transaction) =>
  transaction.status === "paid" || transaction.status === "refunded"
    ? transaction.amount_minor - transaction.refunded_minor
    : 0;
