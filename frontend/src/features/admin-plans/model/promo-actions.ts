"use client";

import { toast } from "sonner";

import { businessToday } from "@/features/admin-sign-in/model/business-zone";
import { apiErrorDescription } from "@/lib/api/error-description";

import { plansApi } from "../api/plans-api";
import { type PromoCode, type PromoCodeDraft, promoStatus } from "../domain/contract";
import type { PromoFormTarget } from "../domain/promo-form-values";
import { attempt } from "./plan-actions";
import { dropPromo, putPromo } from "./plans-store";

/** Creates, updates or copies a code and puts the saved one into the list; resolves to an error message or null. */
export function savePromo(target: PromoFormTarget, draft: PromoCodeDraft) {
  return attempt(async () => {
    const saved =
      target.mode === "edit" ? await plansApi.updatePromo(target.promo.id, draft) : await plansApi.createPromo(draft);
    putPromo(saved);
    toast.success(target.mode === "edit" ? `Промокод ${saved.code} сохранён` : `Промокод ${saved.code} создан`);
  }, "Не удалось сохранить промокод.");
}

/** Switches a code on or off at once, rolling back if the server refuses (e.g. its plans are gone). */
export async function setPromoActive(promo: PromoCode, is_active: boolean) {
  putPromo({ ...promo, is_active, status: promoStatus({ ...promo, is_active }, businessToday()) });
  try {
    const saved = await plansApi.updatePromo(promo.id, { is_active });
    putPromo(saved);
    toast.success(is_active ? `Промокод ${promo.code} включён` : `Промокод ${promo.code} отключён`);
  } catch (error) {
    putPromo(promo);
    toast.error(`Не удалось изменить промокод ${promo.code}`, { description: apiErrorDescription(error) });
  }
}

/** True when deleted. */
export async function removePromo(promo: PromoCode): Promise<boolean> {
  try {
    await plansApi.deletePromo(promo.id);
    dropPromo(promo.id);
    toast.success(`Промокод ${promo.code} удалён`);
    return true;
  } catch (error) {
    toast.error(`Не удалось удалить промокод ${promo.code}`, { description: apiErrorDescription(error) });
    return false;
  }
}
