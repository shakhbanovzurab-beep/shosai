import { NextResponse } from "next/server";

import { detail, forwardToBackend } from "@/server/backend-proxy";

import type { PromoCode, PromoCodesResponse } from "../domain/contract";
import { promoDraftSchema, promoPatchSchema } from "../domain/promo-schema";
import { firstIssue } from "../domain/schema";
import { createPromo, deletePromo, listPromos, patchPromo } from "./promos-repository";

type Context = { params: Promise<{ id: string }> };

const PATH = "/v1/admin/promo-codes";
const backendPath = (id: string) => `${PATH}/${encodeURIComponent(id)}`;

/** `/api/admin/promo-codes`: the promo code list and new codes. */
export const promoCodesRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    return NextResponse.json<PromoCodesResponse>({ promo_codes: listPromos() });
  },

  async POST(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    const body = promoDraftSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(firstIssue(body.error, "Проверьте данные промокода."), 422);
    const created = createPromo(body.data);
    if (!created.ok) return detail(created.message, created.status);
    return NextResponse.json<PromoCode>(created.value, { status: 201 });
  },
};

/** `/api/admin/promo-codes/{id}`: edits or deletes one promo code. */
export const promoCodeRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, backendPath(id));
    if (upstream) return upstream;
    const patch = promoPatchSchema.safeParse(await request.json().catch(() => null));
    if (!patch.success) return detail(firstIssue(patch.error, "Проверьте данные промокода."), 422);
    const saved = patchPromo(id, patch.data);
    return saved.ok ? NextResponse.json<PromoCode>(saved.value) : detail(saved.message, saved.status);
  },

  async DELETE(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, backendPath(id));
    if (upstream) return upstream;
    return deletePromo(id) ? new Response(null, { status: 204 }) : detail("Промокод не найден.", 404);
  },
};
