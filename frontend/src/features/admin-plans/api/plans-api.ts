import { apiRequest, jsonBody } from "@/lib/api-client";

import type {
  Plan,
  PlanDeleteResponse,
  PlanDraft,
  PlanPatch,
  PlansResponse,
  PromoCode,
  PromoCodeDraft,
  PromoCodePatch,
  PromoCodesResponse,
} from "../domain/contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/admin${path}`, init);
const at = (base: string, id: string) => `${base}/${encodeURIComponent(id)}`;

export const plansApi = {
  listPlans: () => request<PlansResponse>("/plans"),
  createPlan: (draft: PlanDraft) => request<Plan>("/plans", jsonBody("POST", draft)),
  updatePlan: (id: string, patch: PlanPatch) => request<Plan>(at("/plans", id), jsonBody("PATCH", patch)),
  deletePlan: (id: string) => request<PlanDeleteResponse>(at("/plans", id), { method: "DELETE" }),
  listPromos: () => request<PromoCodesResponse>("/promo-codes"),
  createPromo: (draft: PromoCodeDraft) => request<PromoCode>("/promo-codes", jsonBody("POST", draft)),
  updatePromo: (id: string, patch: PromoCodePatch) =>
    request<PromoCode>(at("/promo-codes", id), jsonBody("PATCH", patch)),
  deletePromo: (id: string) => request<void>(at("/promo-codes", id), { method: "DELETE" }),
};
