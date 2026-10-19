import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { type FactsPage, type MemoryFact, STATEMENT_MAX } from "../domain/contract";
import { demoFacts } from "./demo-facts";

/*
 * /v1/agent/memory в демо, как его опишет бэкенд `memory` (Leo §13.2, ADR 0030): страницы по курсору, правка
 * текста заменяет факт новым (supersession), «забыть» убирает факт из списка.
 */

const PAGE = 50;
const updateSchema = z.strictObject({
  statement: z.string().trim().min(1).max(STATEMENT_MAX).optional(),
  pinned: z.boolean().optional(),
});

type Ctx = { params: Promise<{ id: string }> };

function refuse(code: string, status: number) {
  const error = { code, request_id: `demo-${crypto.randomUUID()}` };
  return JsonResponse.json({ error, detail: code }, { status });
}

const missing = () => refuse("memory_fact_not_found", 404);

/** /v1/agent/memory */
export const factsRoute = {
  async GET(request: Request) {
    const start = Number(new URL(request.url).searchParams.get("cursor") ?? "0") || 0;
    const facts = [...demoFacts.values()].toSorted((a, b) => b.created_at.localeCompare(a.created_at));
    const next = start + PAGE < facts.length ? String(start + PAGE) : null;
    return JsonResponse.json<FactsPage>({ facts: facts.slice(start, start + PAGE), next_cursor: next });
  },
  async DELETE(_request: Request) {
    demoFacts.clear();
    return new Response(null, { status: 204 });
  },
};

/** /v1/agent/memory/{id} */
export const factRoute = {
  async PATCH(request: Request, { params }: Ctx) {
    const { id } = await params;
    const current = demoFacts.get(id);
    if (!current) return missing();
    const body = updateSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse("memory_fact_invalid", 422);
    const { statement, pinned } = body.data;
    let next: MemoryFact = { ...current, pinned: pinned ?? current.pinned };
    if (statement !== undefined && statement !== current.statement) {
      // Новый текст закрывает старый факт и открывает новый: newer wins, история остаётся у бэкенда.
      demoFacts.delete(id);
      next = { ...next, id: crypto.randomUUID(), statement, source: { kind: "user_edit", title: null } };
      next.created_at = new Date().toISOString();
    }
    demoFacts.set(next.id, next);
    return JsonResponse.json<MemoryFact>(next);
  },
  async DELETE(_request: Request, { params }: Ctx) {
    const { id } = await params;
    return demoFacts.delete(id) ? new Response(null, { status: 204 }) : missing();
  },
};

/** /v1/agent/memory/{id}/accept */
export const acceptRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const { id } = await params;
    const current = demoFacts.get(id);
    if (!current) return missing();
    const accepted: MemoryFact = { ...current, status: "active" };
    demoFacts.set(id, accepted);
    return JsonResponse.json<MemoryFact>(accepted);
  },
};
