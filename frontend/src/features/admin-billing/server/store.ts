import { generateCharges } from "./charges";
import { generateCustomers } from "./customers";
import { createRandom } from "./random";
import type { Store } from "./types";

/*
 * In-memory platform billing for the demo. A year of subscriptions is simulated once per process from a
 * seeded random generator, so every number on the page — KPIs, the revenue chart, the status summary,
 * payouts — is derived from the same transactions. Shared through globalThis to survive hot reloads.
 */

function simulate(now: number): Store {
  const random = createRandom(20_261_005);
  const today = new Date(now);
  const windowStart = Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - 11, 1);
  const customers = generateCustomers(random, now, windowStart);
  return { customers, ...generateCharges(random, customers, now, windowStart) };
}

// Versioned key: the single-currency store of an earlier build may still live in a running dev server.
const shared = globalThis as typeof globalThis & { adminDemoBillingV2?: Store };

export function store(): Store {
  shared.adminDemoBillingV2 ??= simulate(Date.now());
  return shared.adminDemoBillingV2;
}

/** Net of refunds; only settled payments count as revenue. */
export const netMinor = (transaction: { status: string; amount_minor: number; refunded_minor: number }) =>
  transaction.status === "paid" || transaction.status === "refunded"
    ? transaction.amount_minor - transaction.refunded_minor
    : 0;
