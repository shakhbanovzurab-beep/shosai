"use client";

import { useSyncExternalStore } from "react";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { proposalsApi } from "../api/proposals-api";
import { isPending, type LeoProposal, laterOf } from "../domain/proposals";

/*
 * Карточки Leo в двух местах — в разговоре и в «Нужны вы» на главной. Решение или итог в одном месте сразу видны
 * в другом: здесь последнее известное состояние каждой карточки и то, что сейчас в работе.
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

/** Карточка в её самом позднем известном состоянии и занята ли она запросом. */
export function useProposal(proposal: LeoProposal) {
  const state = useSyncExternalStore(
    subscribe,
    () => snapshot,
    () => snapshot,
  );
  const known = state.latest.get(proposal.id);
  return { proposal: known ? laterOf(known, proposal) : proposal, busy: state.busy.has(proposal.id) };
}

/** Появилась новая карточка: список «Нужны вы» перечитывается. */
export const proposalArrived = () => void pendingResource.refresh();

/** Новое состояние карточки от сервера: ответ на решение, `action.updated` или перечитанная карточка. */
export function receiveCard(card: LeoProposal) {
  set((s) => {
    const known = s.latest.get(card.id);
    return { ...s, latest: new Map([...s.latest, [card.id, known ? laterOf(known, card) : card]]) };
  });
  if (!isPending(card))
    pendingResource.update((page) => ({ ...page, items: page.items.filter((item) => item.id !== card.id) }));
}

/** Карточка ждёт ответа на решение: кнопки заняты. */
export function markBusy(id: string, busy: boolean) {
  set((s) => ({ ...s, busy: busy ? new Set([...s.busy, id]) : new Set([...s.busy].filter((known) => known !== id)) }));
}
