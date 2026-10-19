import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import type { LeoProposal } from "../domain/proposals";
import { decideProposal, demoProposals } from "./demo-proposals";

/*
 * /v1/agent/actions в демо (Leo §13.2): список ожидающих и решение по одному. Одобрение «выполняется» с
 * небольшой задержкой, как настоящая запись.
 */

type Ctx = { params: Promise<{ id: string }> };

const approveSchema = z.object({ accepted_changes: z.array(z.int().min(0)).optional() });

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function gone() {
  const code = "action_not_pending";
  return JsonResponse.json(
    { error: { code, request_id: `demo-${crypto.randomUUID()}` }, detail: code },
    { status: 409 },
  );
}

/** /v1/agent/actions?status=proposed */
export const proposalsRoute = {
  async GET(request: Request) {
    const status = new URL(request.url).searchParams.get("status");
    const actions = [...demoProposals.values()]
      .filter((p) => status === null || p.status === status)
      .toSorted((a, b) => b.created_at.localeCompare(a.created_at));
    return JsonResponse.json({ actions, next_cursor: null });
  },
};

/** /v1/agent/actions/{id}/approve */
export const approveRoute = {
  async POST(request: Request, { params }: Ctx) {
    const { id } = await params;
    const body = approveSchema.safeParse(await request.json().catch(() => ({})));
    await pause(900);
    const decided = decideProposal(id, true, body.success ? (body.data.accepted_changes?.length ?? 0) : 0);
    return decided ? JsonResponse.json<LeoProposal>(decided) : gone();
  },
};

/** /v1/agent/actions/{id}/reject */
export const rejectRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const { id } = await params;
    const decided = decideProposal(id, false, 0);
    return decided ? JsonResponse.json<LeoProposal>(decided) : gone();
  },
};
