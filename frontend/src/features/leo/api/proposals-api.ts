import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";
import { apiRequest, jsonBody } from "@/lib/api/request";

import type { DecidedProposal, LeoProposal } from "../domain/proposals";

/* Карточки Leo (Leo §13.2, `/v1/agent/actions*`): что ждёт человека, одна карточка, «Одобрить» и «Отклонить». */

// «Нужны вы» читает одну страницу: карточки живут час, больше сотни разом не ждёт никто.
const PENDING_LIMIT = 100;

/**
 * Тело решения. `accepted_changes` — какие замены превью-сравнения человек взял; сервер примет его с первым
 * инструментом, правящим текст (AG-D10), а до того и не присылает превью-сравнений.
 */
type DecisionBody = components["schemas"]["DecisionBody"] & { accepted_changes?: number[] };

const path = (id: string) => ({ params: { path: { action_id: id } } });

export const proposalsApi = {
  pending: (): Promise<{ items: LeoProposal[]; next_cursor: string | null }> =>
    dataOf(apiClient.GET("/v1/agent/actions", { params: { query: { status: "proposed", limit: PENDING_LIMIT } } })),

  card: (id: string): Promise<LeoProposal> => dataOf(apiClient.GET("/v1/agent/actions/{action_id}", path(id))),

  approve: (proposal: LeoProposal, acceptedChanges?: number[]): Promise<DecidedProposal> => {
    const body: DecisionBody =
      acceptedChanges === undefined
        ? { nonce: proposal.nonce }
        : { nonce: proposal.nonce, accepted_changes: acceptedChanges };
    return dataOf(apiClient.POST("/v1/agent/actions/{action_id}/approve", { ...path(proposal.id), body }));
  },

  reject: (proposal: LeoProposal): Promise<DecidedProposal> =>
    dataOf(
      apiClient.POST("/v1/agent/actions/{action_id}/reject", { ...path(proposal.id), body: { nonce: proposal.nonce } }),
    ),

  /** Карточка `tasks.create` из пунктов дайджеста чата — без вызова модели (CF-D5, AG-R2); путь среза chats. */
  fromDigest: (
    ref: { workspaceId: string; chatId: string; digestId: string },
    itemIds: string[],
  ): Promise<LeoProposal> =>
    apiRequest(
      `/v1/workspaces/${encodeURIComponent(ref.workspaceId)}/chats/${encodeURIComponent(ref.chatId)}/digests/${encodeURIComponent(ref.digestId)}/task-proposals`,
      jsonBody("POST", { item_ids: itemIds }),
    ),
};
