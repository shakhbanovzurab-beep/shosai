"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { chatsApi } from "../api/chats-api";
import { type ChatDigest, type DigestRef, digestItems } from "../domain/digest-contract";

/*
 * Дайджесты в разговоре Leo (chats §1.3): по ресурсу на дайджест, грузится при первом показе карточки. Пункты,
 * отданные в карточку одобрения, отмечаются сразу; когда по карточке решили, дайджест перечитывается — сервер
 * записал задачи или освободил пункты.
 */

/** Что даёт карточке разговор Leo: карточку одобрения из пунктов и переход к ней. */
export type DigestTaskHost = {
  /** Ид карточки одобрения или null, если не вышло (о сбое разговор уже сказал). */
  makeTasks: (itemIds: string[]) => Promise<string | null>;
  showProposal: (proposalId: string) => void;
};

const resources = new Map<string, PollingResource<ChatDigest>>();

export function digestResource({ workspaceId, chatId, digestId }: DigestRef): PollingResource<ChatDigest> {
  const key = `${workspaceId}/${chatId}/${digestId}`;
  let resource = resources.get(key);
  if (!resource) {
    resource = createPollingResource(() => chatsApi(workspaceId).digest(chatId, digestId));
    resources.set(key, resource);
  }
  return resource;
}

export const useDigest = (ref: DigestRef) => usePollingResource(digestResource(ref));

/** Пункты ушли в карточку одобрения: «Ждёт вашего одобрения» видно, не дожидаясь перечитывания. */
export function markItemsProposed(ref: DigestRef, itemIds: readonly string[], proposalId: string) {
  const taken = new Set(itemIds);
  const mark = <T extends { id: string; proposal_id: string | null }>(items: T[]) =>
    items.map((item) => (taken.has(item.id) ? { ...item, proposal_id: proposalId } : item));
  digestResource(ref).update((digest) => ({
    ...digest,
    decisions: mark(digest.decisions),
    questions: mark(digest.questions),
    promises: mark(digest.promises),
  }));
}

/** По карточке одобрения решили: перечитать дайджесты, чьи пункты в ней. */
export function digestProposalDecided(proposalId: string) {
  for (const resource of resources.values()) {
    const state = resource.getSnapshot();
    if (state.status !== "ready") continue;
    if (digestItems(state.data).some((item) => item.proposal_id === proposalId)) void resource.reload();
  }
}
