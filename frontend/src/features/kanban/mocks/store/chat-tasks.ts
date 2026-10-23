import { addWorkspaceTask } from "@/features/workspace/mocks/personal";

import type { TaskChatSource } from "../../domain/tasks-contract";
import { demo } from "./state";

/*
 * Задачи из командного чата (TK-D13), когда агент выполняет одобренную карточку «Сделать задачей»: задача
 * пространства живёт в его моках, здесь — её источник, чтобы моки чатов и Лео видели строку чата.
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
    demo().tasks.set(created.id, {
      id: created.id,
      title: draft.title,
      due_on: draft.due_on,
      assignee,
      space: { workspace_id: workspace.id, workspace_slug: workspace.slug, workspace_name: workspace.name },
      source: { kind: "chat", meeting: null, finding: null, chat: draft.chat },
      created_at: new Date().toISOString(),
    });
    return created.id;
  });
}
