"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";
import { pluralizeRu } from "@/lib/plural";

import { plansApi } from "../api/plans-api";
import type { Plan, PlanDraft } from "../domain/contract";
import { dropPlan, promosResource, putPlan } from "./plans-store";

/** Runs a request; resolves to null on success or the error message to show. */
export async function attempt(run: () => Promise<void>, fallback: string): Promise<string | null> {
  try {
    await run();
    return null;
  } catch (error) {
    return errorMessage(error) ?? fallback;
  }
}

/** Sends the draft and puts the saved plan into the list; resolves to an error message or null. */
export function savePlan(plan: Plan | null, draft: PlanDraft) {
  return attempt(async () => {
    const saved = plan ? await plansApi.updatePlan(plan.id, draft) : await plansApi.createPlan(draft);
    putPlan(saved);
    toast.success(plan ? `Тариф «${saved.name}» сохранён` : `Тариф «${saved.name}» создан`);
  }, "Не удалось сохранить тариф.");
}

/** Switches a plan on or off at once, rolling back if the server refuses. */
export async function setPlanActive(plan: Plan, is_active: boolean) {
  putPlan({ ...plan, is_active });
  try {
    putPlan(await plansApi.updatePlan(plan.id, { is_active }));
  } catch (error) {
    putPlan(plan);
    toast.error(`Не удалось изменить тариф «${plan.name}»`, { description: apiErrorDescription(error) });
  }
}

export async function restorePlan(plan: Plan) {
  try {
    putPlan(await plansApi.updatePlan(plan.id, { archived: false }));
    toast.success(`Тариф «${plan.name}» восстановлен`, {
      description: "Он выключен — включите его, чтобы открыть продажи.",
    });
  } catch (error) {
    toast.error(`Не удалось восстановить тариф «${plan.name}»`, { description: apiErrorDescription(error) });
  }
}

/** Deletes or archives (the server decides by subscribers); true when done. */
export async function removePlan(plan: Plan): Promise<boolean> {
  try {
    const outcome = await plansApi.deletePlan(plan.id);
    if (outcome.result === "archived") {
      putPlan(outcome.plan);
      toast.success(`Тариф «${plan.name}» перенесён в архив`);
    } else {
      dropPlan(plan.id);
      const updated = outcome.promo_codes_updated;
      toast.success(`Тариф «${plan.name}» удалён`, {
        description:
          updated > 0
            ? `Он убран из ${updated} ${pluralizeRu(updated, ["промокода", "промокодов", "промокодов"])}.`
            : undefined,
      });
      // Scopes changed on the server; reload promo codes so they match.
      if (updated > 0) void promosResource.refresh();
    }
    return true;
  } catch (error) {
    toast.error(`Не удалось удалить тариф «${plan.name}»`, { description: apiErrorDescription(error) });
    return false;
  }
}
