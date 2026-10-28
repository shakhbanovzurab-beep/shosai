import { useSyncExternalStore } from "react";

import type { BroadcastSession, BroadcastSnapshot } from "../domain/broadcast";

/** Состояние трансляции для React: эфир, сцена, очереди и чат. */
export function useBroadcastSnapshot(session: BroadcastSession): BroadcastSnapshot {
  return useSyncExternalStore(
    (listener) => session.subscribe(listener),
    () => session.snapshot(),
  );
}
