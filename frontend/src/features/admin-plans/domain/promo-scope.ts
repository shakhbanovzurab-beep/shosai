import type { Plan, PromoCode } from "./contract";

export type ScopeHealth =
  | { kind: "ok" }
  /** Some of its plans are archived or removed; the code still works for the rest. */
  | { kind: "partial"; unavailable: number }
  /** None of its plans can be bought: the code can't be applied anywhere. */
  | { kind: "none" };

/** Whether a scoped code still points at plans customers can buy. */
export function scopeHealth(promo: PromoCode, plansById: ReadonlyMap<string, Plan>): ScopeHealth {
  if (promo.scope === "all") return { kind: "ok" };
  let unavailable = 0;
  for (const id of promo.plan_ids) if (plansById.get(id)?.archived !== false) unavailable += 1;
  if (promo.plan_ids.length === 0 || unavailable === promo.plan_ids.length) return { kind: "none" };
  return unavailable > 0 ? { kind: "partial", unavailable } : { kind: "ok" };
}
