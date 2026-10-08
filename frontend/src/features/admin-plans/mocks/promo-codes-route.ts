import { detail, JsonResponse } from "@/mocks/runtime";

import type { PromoCode, PromoCodesResponse } from "../domain/contract";
import { promoDraftSchema, promoPatchSchema } from "../domain/promo-schema";
import { firstIssue } from "../domain/schema";
import { createPromo, deletePromo, listPromos, patchPromo } from "./promos-repository";

type Context = { params: Promise<{ id: string }> };

/** `/api/admin/promo-codes`: the promo code list and new codes. */
export const promoCodesRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<PromoCodesResponse>({ promo_codes: listPromos() });
  },

  async POST(request: Request) {
    const body = promoDraftSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(firstIssue(body.error, "Проверьте данные промокода."), 422);
    const created = createPromo(body.data);
    if (!created.ok) return detail(created.message, created.status);
    return JsonResponse.json<PromoCode>(created.value, { status: 201 });
  },
};

/** `/api/admin/promo-codes/{id}`: edits or deletes one promo code. */
export const promoCodeRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const patch = promoPatchSchema.safeParse(await request.json().catch(() => null));
    if (!patch.success) return detail(firstIssue(patch.error, "Проверьте данные промокода."), 422);
    const saved = patchPromo(id, patch.data);
    return saved.ok ? JsonResponse.json<PromoCode>(saved.value) : detail(saved.message, saved.status);
  },

  async DELETE(_request: Request, { params }: Context) {
    const { id } = await params;
    return deletePromo(id) ? new Response(null, { status: 204 }) : detail("Промокод не найден.", 404);
  },
};
