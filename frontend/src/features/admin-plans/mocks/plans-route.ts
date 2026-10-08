import { detail, JsonResponse } from "@/mocks/runtime";

import type { Plan, PlanDeleteResponse, PlansResponse } from "../domain/contract";
import { planDraftSchema, planPatchSchema } from "../domain/plan-schema";
import { firstIssue } from "../domain/schema";
import { createPlan, deletePlan, listPlans, patchPlan } from "./plans-repository";

type Context = { params: Promise<{ id: string }> };

/** `/api/admin/plans`: the plan list and new plans. */
export const plansRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<PlansResponse>({ plans: listPlans() });
  },

  async POST(request: Request) {
    const body = planDraftSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(firstIssue(body.error, "Проверьте данные тарифа."), 422);
    const created = createPlan(body.data);
    if (!created.ok) return detail(created.message, created.status);
    return JsonResponse.json<Plan>(created.value, { status: 201 });
  },
};

/** `/api/admin/plans/{id}`: edits, restores, deletes or archives one plan. */
export const planRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const patch = planPatchSchema.safeParse(await request.json().catch(() => null));
    if (!patch.success) return detail(firstIssue(patch.error, "Проверьте данные тарифа."), 422);
    const saved = patchPlan(id, patch.data);
    return saved.ok ? JsonResponse.json<Plan>(saved.value) : detail(saved.message, saved.status);
  },

  /** Deletes a plan without subscribers; archives one that has them. */
  async DELETE(_request: Request, { params }: Context) {
    const { id } = await params;
    const outcome = deletePlan(id);
    return outcome.ok ? JsonResponse.json<PlanDeleteResponse>(outcome.value) : detail(outcome.message, outcome.status);
  },
};
