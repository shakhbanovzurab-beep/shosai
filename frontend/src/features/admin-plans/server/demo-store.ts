import type { Plan } from "../domain/contract";
import { seedPlans } from "./demo-seed";
import { type StoredPromo, seedPromos } from "./demo-seed-promos";

/*
 * In-memory plans and promo codes for the demo, shared across route handlers through globalThis.
 * `plans-repository.ts` and `promos-repository.ts` hold the rules a real backend must enforce too:
 * unique slugs and codes, archive-instead-of-delete for plans with subscribers, and promo scopes that
 * never point at a removed plan.
 */

type Store = { plans: Map<string, Plan>; promos: Map<string, StoredPromo> };

export type Outcome<T> = { ok: true; value: T } | { ok: false; status: number; message: string };
export const fail = (status: number, message: string): Outcome<never> => ({ ok: false, status, message });
export const ok = <T>(value: T): Outcome<T> => ({ ok: true, value });

const seed = (): Store => ({
  plans: new Map(seedPlans().map((plan) => [plan.id, plan])),
  promos: new Map(seedPromos().map((promo) => [promo.id, promo])),
});

const shared = globalThis as typeof globalThis & { adminDemoPlansV4?: Store };
shared.adminDemoPlansV4 ??= seed();
export const store = shared.adminDemoPlansV4;

export const now = () => new Date().toISOString();
