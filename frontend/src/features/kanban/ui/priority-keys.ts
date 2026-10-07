import type { TaskPriority } from "../domain/board";

/** Each priority's key in the `kanban.priority` catalog; the API's values ("High"…) stay as they are. */
export const PRIORITY_KEYS = { High: "high", Medium: "medium", Low: "low" } as const satisfies Record<
  TaskPriority,
  string
>;
