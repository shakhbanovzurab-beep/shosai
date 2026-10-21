"use client";

import { createContext, type ReactNode, use, useEffect, useState } from "react";

import { useTranslations } from "use-intl";

import { NameDialog, type NameRequest } from "@/components/name-dialog";

import type { BoardDetail } from "../domain/boards-contract";
import { BoardStoreContext, useBoardSelector } from "../model/board-hooks";
import { createBoardStore } from "../model/board-store";
import { type CardCommands, createCardCommands } from "../model/card-commands";
import { type ColumnCommands, createColumnCommands } from "../model/column-commands";
import type { CommandWords } from "../model/command-context";

/*
 * Доска, которую человек правит: хранилище создаётся один раз на доску, новые версии с сервера принимаются в него
 * (панель и фокус не теряются); команды работают с хранилищем и словами на языке человека.
 */

type BoardCommandsValue = { cards: CardCommands; columns: ColumnCommands };

const BoardCommandsContext = createContext<BoardCommandsValue | null>(null);

export function useBoardCommands() {
  const value = use(BoardCommandsContext);
  if (!value) throw new Error("useBoardCommands must be used inside <BoardProvider>");
  return value;
}

/** Доска Jira только читается, пока идёт первая синхронизация или синхронизация остановлена. */
export const useEditable = () =>
  useBoardSelector(({ summary: { jira } }) => !jira || (jira.sync_status !== "error" && jira.last_synced_at !== null));

/** Колонки доски Jira — её, удаление и копии задач делают в Jira. */
export const useManagedByJira = () => useBoardSelector((s) => s.summary.jira !== null);

export function BoardProvider({ detail, children }: { detail: BoardDetail; children: ReactNode }) {
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const ta = useTranslations("kanbanApi");
  const [nameRequest, setNameRequest] = useState<NameRequest | null>(null);
  const [store] = useState(() => createBoardStore(detail));
  // Команды пересоздаются, только когда меняется язык: React Compiler запоминает их по store и переводчикам.
  const ctx = { store, words: (): CommandWords => ({ t, tc, ta }), askName: setNameRequest };
  const cards = createCardCommands(ctx);
  const commands: BoardCommandsValue = { cards, columns: createColumnCommands(ctx, cards) };

  // Версия с сервера (опрос Jira, перечитывание) ложится в то же хранилище.
  useEffect(() => store.receive(detail), [store, detail]);

  return (
    <BoardStoreContext value={store}>
      <BoardCommandsContext value={commands}>
        {children}
        <NameDialog request={nameRequest} onClose={() => setNameRequest(null)} />
      </BoardCommandsContext>
    </BoardStoreContext>
  );
}
