import { useSyncExternalStore } from "react";

import type { BoardSession, BoardState } from "../domain/board";

/** Состояние доски для React: сохранение, только чтение, курсоры других. */
export function useBoardState(board: BoardSession): BoardState {
  return useSyncExternalStore(
    (listener) => board.subscribe(listener),
    () => board.state(),
  );
}
