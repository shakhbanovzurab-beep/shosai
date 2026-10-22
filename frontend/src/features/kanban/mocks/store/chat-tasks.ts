import { addWorkspaceTask } from "@/features/workspace/mocks/personal";

import type { TaskChatSource } from "../../domain/tasks-contract";
import { fromChat, seedTask } from "../seed/builders";
import { demo } from "./state";

/*
 * Задачи из командного чата (TK-D13), когда агент выполняет одобренную карточку «Сделать задачей»: задача
 * пространства живёт в его моках, здесь — её источник, чтобы доска и панель показали строку чата.
 */

export type ChatTaskDraft = {
  workspace_id: string;
  title: string;
  due_on: string | null;
  project_id: string | null;
  /** Аккаунт участника, если имя из чата сопоставилось. */
  assignee_account: string | null;
  chat: TaskChatSource;
};

/** Ид созданных задач в порядке черновиков; черновик пространства, куда нет доступа, пропускается. */
export function createChatTasks(drafts: readonly ChatTaskDraft[]): (string | null)[] {
  return drafts.map((draft) => {
    const created = addWorkspaceTask(draft.workspace_id, draft);
    if (!created) return null;
    const { workspace, assignee } = created;
    const task = seedTask(created.id, draft.title, "", {
      due_on: draft.due_on,
      assignee,
      space: { workspace_id: workspace.id, workspace_slug: workspace.slug, workspace_name: workspace.name },
      source: fromChat(draft.chat),
      created_at: new Date().toISOString(),
    });
    task.updated_at = task.created_at;
    demo().tasks.set(task.id, task);
    return task.id;
  });
}
