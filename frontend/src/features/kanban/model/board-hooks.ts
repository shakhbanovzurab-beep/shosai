"use client";

import { createContext, use, useSyncExternalStore } from "react";

import type { BoardSnapshot, BoardStore } from "./board-store";

/* Подписка компонентов на свою часть доски. Хранилище кладёт в контекст экран доски. */

export const BoardStoreContext = createContext<BoardStore | null>(null);

export function useBoardStore(): BoardStore {
  const store = use(BoardStoreContext);
  if (!store) throw new Error("useBoardStore must be used inside the board's store provider");
  return store;
}

/** Часть доски: компонент перерисуется, только когда она сменится (выбор должен отдавать ту же ссылку). */
export function useBoardSelector<T>(select: (snapshot: BoardSnapshot) => T): T {
  const store = useBoardStore();
  const read = () => select(store.get());
  return useSyncExternalStore(store.subscribe, read, read);
}

const NO_CARDS: string[] = [];

export const useSummary = () => useBoardSelector((s) => s.summary);
export const useColumnOrder = () => useBoardSelector((s) => s.columnOrder);
export const useColumn = (id: string) => useBoardSelector((s) => s.columns[id]);
export const useCardIds = (columnId: string) => useBoardSelector((s) => s.cardIds[columnId] ?? NO_CARDS);
export const useCard = (id: string) => useBoardSelector((s) => s.cards[id]);
export const useBoardStickers = () => useBoardSelector((s) => s.stickers);
