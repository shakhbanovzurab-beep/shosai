"use client";

import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { billingApi } from "../api/billing-api";
import type { Transaction, TransactionsResponse } from "../domain/contract";

export const overviewResource = createPollingResource(billingApi.overview);

/** One resource per filter combination, so going back to a page shows it at once while it refreshes. */
const transactionResources = new Map<string, PollingResource<TransactionsResponse>>();

export function transactionsResource(search: string): PollingResource<TransactionsResponse> {
  let resource = transactionResources.get(search);
  if (!resource) {
    resource = createPollingResource(() => billingApi.transactions(search));
    transactionResources.set(search, resource);
  }
  return resource;
}

/**
 * Refunds a payment, then shows the updated row on the current page right away. Other cached pages may
 * now be stale (a status filter can drop the row), so they are forgotten, and the KPIs are reloaded.
 */
export async function refund(transaction: Transaction, amountMinor: number, search: string) {
  const updated = await billingApi.refund(transaction.id, { amount_minor: amountMinor });
  for (const key of transactionResources.keys()) if (key !== search) transactionResources.delete(key);
  transactionResources.get(search)?.update((data) => ({
    ...data,
    items: data.items.map((item) => (item.id === updated.id ? updated : item)),
  }));
  void overviewResource.refresh();
  return updated;
}
