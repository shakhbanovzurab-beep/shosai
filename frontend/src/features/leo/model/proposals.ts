"use client";

import { useSyncExternalStore } from "react";

import { toast } from "sonner";

import { digestProposalDecided } from "@/features/chats/model/digests";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { apiErrorDescription } from "@/lib/api/error-description";
import { createPollingResource } from "@/lib/polling-resource";

import { proposalsApi } from "../api/proposals-api";
import type { LeoProposal } from "../domain/proposals";

/*
 * Предложения Leo в двух местах — карточкой в чате и в «Нужны вы» на главной. Решение в одном месте сразу видно
 * в другом: здесь хранится последнее известное состояние каждого предложения и то, что сейчас в работе.
 */

/** Ожидающие решения из чатов, поручений и MCP — список «Нужны вы». */
export const pendingResource = createPollingResource(proposalsApi.pending);

export const usePendingProposals = () => usePollingResource(pendingResource);

type Snapshot = { latest: ReadonlyMap<string, LeoProposal>; busy: ReadonlySet<string> };

let snapshot: Snapshot = { latest: new Map(), busy: new Set() };
const listeners = new Set<() => void>();

function set(change: (current: Snapshot) => Snapshot) {
  snapshot = change(snapshot);
  for (const listener of listeners) listener();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Предложение в его последнем состоянии и занято ли оно запросом. */
export function useProposal(proposal: LeoProposal) {
  const state = useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => snapshot,
  );
  return { proposal: state.latest.get(proposal.id) ?? proposal, busy: state.busy.has(proposal.id) };
}

/** В чате появилось новое предложение: список «Нужны вы» перечитывается. */
export const proposalArrived = () => void pendingResource.refresh();

type Words = { failed: string };

async function decide(proposal: LeoProposal, request: () => Promise<LeoProposal>, words: Words) {
  set((s) => ({ ...s, busy: new Set([...s.busy, proposal.id]) }));
  try {
    const decided = await request();
    set((s) => ({ ...s, latest: new Map([...s.latest, [decided.id, decided]]) }));
    // Карточку могли собрать из пунктов дайджеста: он перечитается и покажет задачи или свободные пункты.
    digestProposalDecided(decided.id);
    pendingResource.update((page) => ({ ...page, actions: page.actions.filter((a) => a.id !== decided.id) }));
  } catch (error) {
    toast.error(words.failed, { description: apiErrorDescription(error) });
  } finally {
    set((s) => ({ ...s, busy: new Set([...s.busy].filter((id) => id !== proposal.id)) }));
  }
}

/** «Одобрить»: для правки текста — только выбранные замены. */
export const approveProposal = (proposal: LeoProposal, acceptedChanges: number[] | undefined, words: Words) =>
  decide(proposal, () => proposalsApi.approve(proposal.id, acceptedChanges), words);

export const rejectProposal = (proposal: LeoProposal, words: Words) =>
  decide(proposal, () => proposalsApi.reject(proposal.id), words);
