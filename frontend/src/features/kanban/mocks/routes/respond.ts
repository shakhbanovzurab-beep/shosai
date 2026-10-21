import { reconcile } from "../store/landing";
import type { Outcome } from "../store/outcome";
import { findBoard, findTask } from "../store/state";
import type { StoredBoard, StoredTask } from "../store/types";
import { json, noContent, refuse } from "./http";

/* Общие шаги маршрутов: найти доску или задачу (после сверки, как при чтении на сервере) и ответить исходом. */

export async function withBoard(
  params: Promise<{ id: string }>,
  run: (board: StoredBoard) => Response | Promise<Response>,
) {
  reconcile();
  const board = findBoard((await params).id);
  return board ? run(board) : refuse("board_not_found");
}

export async function withTask(
  params: Promise<{ id: string }>,
  run: (task: StoredTask) => Response | Promise<Response>,
) {
  reconcile();
  const task = findTask((await params).id);
  return task ? run(task) : refuse("task_not_found");
}

/** Исход операции: значение в форме контракта (`present`) или отказ с его кодом. */
export function answer<T, R>(outcome: Outcome<T>, present: (value: T) => R, status = 200) {
  return outcome.ok ? json(present(outcome.value), status) : refuse(outcome.code);
}

export const answerEmpty = <T>(outcome: Outcome<T>) => (outcome.ok ? noContent() : refuse(outcome.code));
