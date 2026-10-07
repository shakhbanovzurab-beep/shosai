"use client";

import { createPollingResource } from "@/lib/polling-resource";

import { plansApi } from "../api/plans-api";
import type { Plan, PromoCode } from "../domain/contract";

export const plansResource = createPollingResource(plansApi.listPlans);
export const promosResource = createPollingResource(plansApi.listPromos);

const bySortOrder = (a: Plan, b: Plan) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, "ru");

/** Puts a saved plan into the list (adding it if new), keeping the pricing-page order. */
export const putPlan = (plan: Plan) =>
  plansResource.update((data) => ({
    plans: [...data.plans.filter((p) => p.id !== plan.id), plan].toSorted(bySortOrder),
  }));

export const dropPlan = (id: string) =>
  plansResource.update((data) => ({ plans: data.plans.filter((p) => p.id !== id) }));

/** Puts a saved promo code into the list: replaced in place, or first when new. */
export const putPromo = (promo: PromoCode) =>
  promosResource.update((data) => {
    const exists = data.promo_codes.some((p) => p.id === promo.id);
    return {
      promo_codes: exists ? data.promo_codes.map((p) => (p.id === promo.id ? promo : p)) : [promo, ...data.promo_codes],
    };
  });

export const dropPromo = (id: string) =>
  promosResource.update((data) => ({ promo_codes: data.promo_codes.filter((p) => p.id !== id) }));
