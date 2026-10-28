import { useSyncExternalStore } from "react";

import type { CallSession, CallSnapshot } from "../domain/call-session";

/** Снимок сессии для React; меняется, когда меняется звонок. */
export function useCallSnapshot(session: CallSession): CallSnapshot {
  return useSyncExternalStore(
    (listener) => session.subscribe(listener),
    () => session.snapshot(),
  );
}
