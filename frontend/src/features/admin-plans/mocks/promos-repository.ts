import { businessToday } from "@/features/admin-sign-in/model/business-zone";

import { type PromoCode, type PromoCodeDraft, type PromoCodePatch, promoStatus } from "../domain/contract";
import { promoDraftSchema } from "../domain/promo-schema";
import { firstIssue } from "../domain/schema";
import type { StoredPromo } from "./demo-seed-promos";
import { fail, now, type Outcome, ok, store } from "./demo-store";

/* Promo codes in the in-memory demo: unique codes, and scopes that only name plans on sale. */

const withStatus = (promo: StoredPromo): PromoCode => ({ ...promo, status: promoStatus(promo, businessToday()) });

export const listPromos = () =>
  [...store.promos.values()].toSorted((a, b) => b.created_at.localeCompare(a.created_at)).map(withStatus);

/** `keptPlanIds`: archived plans already in the code's scope, which may stay there. */
function checkPromoRefs(
  draft: PromoCodeDraft,
  exceptId?: string,
  keptPlanIds: ReadonlySet<string> = new Set(),
): Outcome<null> {
  for (const promo of store.promos.values())
    if (promo.code === draft.code && promo.id !== exceptId) return fail(409, `Промокод ${draft.code} уже существует.`);
  for (const planId of draft.plan_ids) {
    const plan = store.plans.get(planId);
    if (!plan) return fail(422, "Один из выбранных тарифов не найден. Обновите страницу.");
    if (plan.archived && !keptPlanIds.has(planId))
      return fail(422, `Тариф «${plan.name}» в архиве — его нельзя добавить в промокод.`);
  }
  return ok(null);
}

export function createPromo(draft: PromoCodeDraft): Outcome<PromoCode> {
  const check = checkPromoRefs(draft);
  if (!check.ok) return check;
  const promo: StoredPromo = { ...draft, id: crypto.randomUUID(), redemptions: 0, created_at: now() };
  store.promos.set(promo.id, promo);
  return ok(withStatus(promo));
}

/** Saves an already merged and validated promo code. Archived plans already in its scope may stay. */
function savePromo(id: string, next: PromoCodeDraft): Outcome<PromoCode> {
  const current = store.promos.get(id);
  if (!current) return fail(404, "Промокод не найден.");
  const check = checkPromoRefs(next, id, new Set(current.plan_ids));
  if (!check.ok) return check;
  if (next.max_redemptions !== null && next.max_redemptions < current.redemptions)
    return fail(422, `Лимит активаций не может быть меньше уже использованных (${current.redemptions}).`);
  const promo: StoredPromo = { ...current, ...next };
  store.promos.set(id, promo);
  return ok(withStatus(promo));
}

function draftOf(promo: StoredPromo): PromoCodeDraft {
  const { id: _id, redemptions: _r, created_at: _c, ...draft } = promo;
  return draft;
}

/** Applies a shape-checked patch: merges it into the code, checks the result as a whole, then saves it. */
export function patchPromo(id: string, patch: PromoCodePatch): Outcome<PromoCode> {
  const current = store.promos.get(id);
  if (!current) return fail(404, "Промокод не найден.");
  const merged = promoDraftSchema.safeParse({ ...draftOf(current), ...patch });
  if (!merged.success) return fail(422, firstIssue(merged.error, "Проверьте данные промокода."));
  return savePromo(id, merged.data);
}

export const deletePromo = (id: string) => store.promos.delete(id);
