import type { Assignee, TaskSource, TaskSpace } from "../../domain/tasks-contract";

/** Задача из командного чата, как её помнят моки, пока у chats нет API (TK-D13). */
export type ChatTaskRecord = {
  id: string;
  title: string;
  due_on: string | null;
  assignee: Assignee | null;
  space: TaskSpace;
  source: TaskSource;
  created_at: string;
};
