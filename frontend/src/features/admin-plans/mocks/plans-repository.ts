import type { Plan, PlanDeleteResponse, PlanDraft, PlanPatch } from "../domain/contract";
import { planDraftSchema } from "../domain/plan-schema";
import { firstIssue } from "../domain/schema";
import { fail, now, type Outcome, ok, store } from "./demo-store";

/* Plans in the in-memory demo: unique slugs, archive-instead-of-delete for plans with subscribers. */

export const listPlans = () =>
  [...store.plans.values()].toSorted((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, "ru"));

function slugTaken(slug: string, exceptId?: string) {
  for (const plan of store.plans.values()) if (plan.slug === slug && plan.id !== exceptId) return true;
  return false;
}

export function createPlan(draft: PlanDraft): Outcome<Plan> {
  if (slugTaken(draft.slug)) return fail(409, `Slug «${draft.slug}» уже занят другим тарифом.`);
  const stamp = now();
  const plan: Plan = {
    ...draft,
    id: crypto.randomUUID(),
    subscribers: 0,
    archived: false,
    created_at: stamp,
    updated_at: stamp,
  };
  store.plans.set(plan.id, plan);
  return ok(plan);
}

/** Saves an already merged and validated plan. Archived plans can only be restored, not edited. */
function savePlan(id: string, next: PlanDraft, archived: boolean | undefined): Outcome<Plan> {
  const current = store.plans.get(id);
  if (!current) return fail(404, "Тариф не найден.");
  const restoring = current.archived && archived === false;
  if (current.archived && !restoring) return fail(409, "Тариф в архиве. Восстановите его, чтобы изменить.");
  if (slugTaken(next.slug, id)) return fail(409, `Slug «${next.slug}» уже занят другим тарифом.`);
  const isArchived = archived ?? current.archived;
  const plan: Plan = {
    ...current,
    ...next,
    // An archived plan is never on sale; a restored one stays off until switched on.
    is_active: isArchived ? false : next.is_active,
    is_featured: isArchived ? false : next.is_featured,
    archived: isArchived,
    updated_at: now(),
  };
  store.plans.set(id, plan);
  return ok(plan);
}

function draftOf(plan: Plan): PlanDraft {
  const { id: _id, subscribers: _s, archived: _a, created_at: _c, updated_at: _u, ...draft } = plan;
  return draft;
}

/** Applies a shape-checked patch: merges it into the plan, checks the result as a whole, then saves it. */
export function patchPlan(id: string, patch: PlanPatch): Outcome<Plan> {
  const current = store.plans.get(id);
  if (!current) return fail(404, "Тариф не найден.");
  const { archived, ...fields } = patch;
  const merged = planDraftSchema.safeParse({ ...draftOf(current), ...fields });
  if (!merged.success) return fail(422, firstIssue(merged.error, "Проверьте данные тарифа."));
  return savePlan(id, merged.data, archived);
}

/** Deletes a plan without subscribers (pruning it from promo scopes); archives one with subscribers. */
export function deletePlan(id: string): Outcome<PlanDeleteResponse> {
  const current = store.plans.get(id);
  if (!current) return fail(404, "Тариф не найден.");
  if (current.subscribers > 0) {
    if (current.archived) return fail(409, "У тарифа есть подписчики, поэтому его нельзя удалить — он уже в архиве.");
    const plan: Plan = { ...current, archived: true, is_active: false, is_featured: false, updated_at: now() };
    store.plans.set(id, plan);
    return ok({ result: "archived", plan, promo_codes_updated: 0 });
  }

  store.plans.delete(id);
  let updated = 0;
  for (const promo of store.promos.values()) {
    const plan_ids = promo.plan_ids.filter((planId) => planId !== id);
    if (plan_ids.length === promo.plan_ids.length) continue;
    // A code scoped to nothing would silently apply to nothing; switch it off so it shows up for review.
    store.promos.set(promo.id, { ...promo, plan_ids, is_active: plan_ids.length > 0 ? promo.is_active : false });
    updated += 1;
  }
  return ok({ result: "deleted", plan: null, promo_codes_updated: updated });
}

/** Plans on sale, in pricing-page order: active and not archived. Read by the customer-facing Upgrade page. */
export const listPublicPlans = () => listPlans().filter((plan) => plan.is_active && !plan.archived);
