"use client";

import { createContext, type ReactNode, use, useEffect, useState } from "react";

import { useTranslations } from "use-intl";

import { NameDialog, type NameRequest } from "@/components/name-dialog";
import { useNow } from "@/hooks/use-now";
import { dayIn } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";

import type { BoardDetail } from "../domain/boards-contract";
import { BoardStoreContext, TodayContext, useBoardSelector } from "../model/board-hooks";
import { createBoardStore } from "../model/board-store";
import { type CardCommands, createCardCommands } from "../model/card-commands";
import { type ColumnCommands, createColumnCommands } from "../model/column-commands";
import { type ColumnLifecycle, createColumnLifecycle } from "../model/column-lifecycle";
import type { CommandWords } from "../model/command-context";
import { createFieldCommands, type FieldCommands } from "../model/field-commands";
import { NewColumnDialog } from "./column-dialog";

/*
 * Доска, которую человек правит: хранилище создаётся один раз на доску, новые версии с сервера принимаются в него
 * (панель и фокус не теряются); команды работают с хранилищем и словами на языке человека.
 */

type BoardCommandsValue = {
  cards: CardCommands;
  columns: ColumnCommands;
  lifecycle: ColumnLifecycle;
  fields: FieldCommands;
  /** Открыть диалог новой колонки на месте `position`. */
  askNewColumn: (position: number) => void;
};

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
  const [newColumnAt, setNewColumnAt] = useState<number | null>(null);
  const [store] = useState(() => createBoardStore(detail));
  // Один таймер на доску, а не на каждую карточку: «сегодня» нужно сроку и «просрочено».
  const now = useNow();
  const zone = useTimeZone();
  const today = now === null ? "" : dayIn(new Date(now), zone);
  // Команды пересоздаются, только когда меняется язык: React Compiler запоминает их по store и переводчикам.
  const ctx = { store, words: (): CommandWords => ({ t, tc, ta }), askName: setNameRequest };
  const cards = createCardCommands(ctx);
  const lifecycle = createColumnLifecycle(ctx);
  const commands: BoardCommandsValue = {
    cards,
    columns: createColumnCommands(ctx, cards),
    lifecycle,
    fields: createFieldCommands(ctx),
    askNewColumn: setNewColumnAt,
  };

  // Версия с сервера (опрос Jira, перечитывание) ложится в то же хранилище.
  useEffect(() => store.receive(detail), [store, detail]);

  return (
    <BoardStoreContext value={store}>
      <TodayContext value={today}>
        <BoardCommandsContext value={commands}>
          {children}
          <NameDialog request={nameRequest} onClose={() => setNameRequest(null)} />
          <NewColumnDialog position={newColumnAt} lifecycle={lifecycle} onClose={() => setNewColumnAt(null)} />
        </BoardCommandsContext>
      </TodayContext>
    </BoardStoreContext>
  );
}
