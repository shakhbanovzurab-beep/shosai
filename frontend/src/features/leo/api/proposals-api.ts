import { apiRequest, jsonBody } from "@/lib/api/request";

import type { LeoProposal } from "../domain/proposals";

// Маршруты Leo §13.2; бэкенда `agent` ещё нет, их отдают моки разработки.
const BASE = "/v1/agent/actions";
const action = (id: string) => `${BASE}/${encodeURIComponent(id)}`;

export type ProposalsPage = { actions: LeoProposal[]; next_cursor: string | null };

/** Approvals of Leo's actions (ADR 0025): what waits for the person, approve, decline. */
export const proposalsApi = {
  pending: (): Promise<ProposalsPage> => apiRequest(`${BASE}?status=proposed`),
  /** `accepted_changes` — какие правки из превью-сравнения человек принял (только для правок текста). */
  approve: (id: string, acceptedChanges?: number[]): Promise<LeoProposal> =>
    apiRequest(`${action(id)}/approve`, jsonBody("POST", { accepted_changes: acceptedChanges })),
  reject: (id: string): Promise<LeoProposal> => apiRequest(`${action(id)}/reject`, { method: "POST" }),
  /** Карточка `tasks.create` из пунктов дайджеста чата — без вызова модели (CF-D5, AG-R2). */
  fromDigest: (
    ref: { workspaceId: string; chatId: string; digestId: string },
    itemIds: string[],
  ): Promise<LeoProposal> =>
    apiRequest(
      `/v1/workspaces/${encodeURIComponent(ref.workspaceId)}/chats/${encodeURIComponent(ref.chatId)}/digests/${encodeURIComponent(ref.digestId)}/task-proposals`,
      jsonBody("POST", { item_ids: itemIds }),
    ),
};
