import type { Dispatch, SetStateAction } from "react";

import { toast } from "sonner";

import type { NameRequest } from "@/components/name-dialog";

import { type BoardState, TASK_TITLE_MAX, type TaskPriority } from "../domain/board";
import {
  insertTask,
  locateTask,
  moveTask,
  shiftColumn,
  sortByPriority,
  updateTask,
  withoutTask,
} from "../domain/board-rules";
import { createTask, deleteTasks, patchTask, saveLayout } from "../model/task-actions";
import type { CommonWords, KanbanWords } from "../model/words";

type State = {
  boardId: string;
  board: BoardState;
  setBoard: Dispatch<SetStateAction<BoardState>>;
  columnOrder: string[];
  setColumnOrder: Dispatch<SetStateAction<string[]>>;
  titles: Record<string, string>;
  setTitles: Dispatch<SetStateAction<Record<string, string>>>;
  requestName: (request: NameRequest) => void;
  /** The `kanban` and `common` catalogs, for dialogs and toasts. */
  t: KanbanWords;
  tc: CommonWords;
};

/**
 * What the board's menus, buttons and drag-and-drop do: each change shows at once and is saved; a
 * failed save puts the board back. Deleting waits for the Undo toast to close before it's saved.
 */
export function createBoardCommands(s: State) {
  const { boardId, board, setBoard, t, tc } = s;
  const layout = (order: string[], titles: Record<string, string>, tasks: BoardState) => ({
    columns: order.map((id) => ({ id, title: titles[id] ?? id, task_ids: (tasks[id] ?? []).map((task) => task.id) })),
  });
  const saveLayoutOf = (order: string[], titles: Record<string, string>, tasks: BoardState, revert: () => void) =>
    void saveLayout(boardId, layout(order, titles, tasks), t).then((saved) => (saved ? undefined : revert()));

  /** Removes tasks now; deletes them for good once the toast closes without Undo. */
  function removeWithUndo(message: string, next: BoardState, taskIds: string[]) {
    const before = board;
    let settled = false;
    const commit = () => {
      if (settled) return;
      settled = true;
      void deleteTasks(boardId, taskIds, t).then((done) => (done ? undefined : setBoard(before)));
    };
    setBoard(next);
    toast(message, {
      action: {
        label: tc("actions.undo"),
        onClick: () => {
          settled = true;
          setBoard(before);
        },
      },
      onAutoClose: commit,
      onDismiss: commit,
    });
  }

  return {
    setPriority(taskId: string, priority: TaskPriority) {
      const before = board;
      setBoard(updateTask(board, taskId, { priority }));
      void patchTask(boardId, taskId, { priority }, t).then((ok) => (ok ? undefined : setBoard(before)));
    },
    moveTask(taskId: string, columnId: string, edge: "top" | "bottom") {
      const before = board;
      const next = moveTask(board, taskId, columnId, edge);
      setBoard(next);
      const at = locateTask(next, taskId);
      if (at)
        void patchTask(boardId, taskId, { column_id: columnId, position: at.index }, t).then((ok) =>
          ok ? undefined : setBoard(before),
        );
    },
    /** After a drag: saves where the task landed, if it moved. */
    commitTaskDrop(taskId: string, before: BoardState) {
      const from = locateTask(before, taskId);
      const to = locateTask(board, taskId);
      if (!to || (from && from.columnId === to.columnId && from.index === to.index)) return;
      void patchTask(boardId, taskId, { column_id: to.columnId, position: to.index }, t).then((ok) =>
        ok ? undefined : setBoard(before),
      );
    },
    commitColumnOrder(order: string[], before: string[]) {
      saveLayoutOf(order, s.titles, board, () => s.setColumnOrder(before));
    },
    renameTask(taskId: string) {
      const at = locateTask(board, taskId);
      if (!at) return;
      s.requestName({
        title: t("commands.renameTask"),
        initial: at.task.title,
        submitLabel: tc("actions.rename"),
        onSubmit: (title) => {
          setBoard((b) => updateTask(b, taskId, { title }));
          void patchTask(boardId, taskId, { title }, t).then((ok) =>
            ok ? undefined : setBoard((b) => updateTask(b, taskId, { title: at.task.title })),
          );
        },
      });
    },
    addTask(columnId: string) {
      s.requestName({
        title: t("commands.newTaskIn", { column: s.titles[columnId] ?? "" }),
        initial: "",
        submitLabel: t("addTask"),
        onSubmit: (title) =>
          void createTask(boardId, { column_id: columnId, position: 0, title }, t).then((task) => {
            if (task) setBoard((b) => insertTask(b, columnId, 0, task));
          }),
      });
    },
    duplicateTask(taskId: string) {
      const at = locateTask(board, taskId);
      if (!at) return;
      const copy = { column_id: at.columnId, position: at.index + 1, copy_of: taskId };
      const named = t("commands.copyTitle", { title: at.task.title });
      const title = named.length > TASK_TITLE_MAX ? at.task.title : named;
      void createTask(boardId, { ...copy, title }, t).then((task) =>
        task ? setBoard((b) => insertTask(b, at.columnId, at.index + 1, task)) : undefined,
      );
    },
    deleteTask(taskId: string) {
      const at = locateTask(board, taskId);
      if (at) removeWithUndo(t("commands.deleted", { title: at.task.title }), withoutTask(board, taskId), [taskId]);
    },
    copyTaskLink(taskId: string) {
      const task = locateTask(board, taskId)?.task;
      if (!task) return;
      const params = new URLSearchParams({ board: boardId, task: taskId });
      const url = task.jira?.url ?? `${window.location.origin}/app/kanban?${params}`;
      navigator.clipboard.writeText(url).then(
        () =>
          toast.success(task.jira ? t("commands.jiraLinkCopied", { key: task.jira.key }) : tc("feedback.linkCopied")),
        () => toast.error(tc("feedback.linkCopyFailed")),
      );
    },
    renameColumn(columnId: string) {
      const before = s.titles;
      s.requestName({
        title: t("commands.renameColumn"),
        initial: before[columnId] ?? "",
        submitLabel: tc("actions.rename"),
        onSubmit: (title) => {
          const titles = { ...before, [columnId]: title };
          s.setTitles(titles);
          saveLayoutOf(s.columnOrder, titles, board, () => s.setTitles(before));
        },
      });
    },
    /** One place towards the start (-1) or the end (1) of the board, whichever way the language reads. */
    shiftColumn(columnId: string, by: -1 | 1) {
      const before = s.columnOrder;
      const order = shiftColumn(before, columnId, by);
      s.setColumnOrder(order);
      saveLayoutOf(order, s.titles, board, () => s.setColumnOrder(before));
    },
    sortColumn(columnId: string) {
      const before = board;
      const next = sortByPriority(board, columnId);
      setBoard(next);
      saveLayoutOf(s.columnOrder, s.titles, next, () => setBoard(before));
    },
    /** Workspace task cards stay: they leave when the task is done or reassigned in its workspace. */
    clearColumn(columnId: string) {
      const kept = (board[columnId] ?? []).filter((task) => task.workspace);
      const ids = (board[columnId] ?? []).filter((task) => !task.workspace).map((task) => task.id);
      const message = t("commands.cleared", { count: ids.length, column: s.titles[columnId] ?? "" });
      if (ids.length) removeWithUndo(message, { ...board, [columnId]: kept }, ids);
    },
  };
}

export type BoardCommands = ReturnType<typeof createBoardCommands>;
