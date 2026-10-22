import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { TaskSpace } from "../../domain/tasks-contract";
import { fromChat, inDays, ME_PERSON, minutesAgo, seedTask } from "./builders";

/*
 * Две задачи пространства Lumen, сделанные из командного чата «Release team» (TK-D13): Leo создал их по просьбе
 * в чате. Сами задачи живут в моках пространства (у них те же ид), здесь — их источник и место на доске.
 */

const LUMEN_SPACE: TaskSpace = { workspace_id: LUMEN, workspace_slug: "lumen", workspace_name: "Lumen" };
const RELEASE = { connection_id: "chat-tg-release", messenger: "telegram", chat_title: "Release team" } as const;
const MESSAGE_LINK = "https://t.me/c/2093847561";

export const chatTasks = () => ({
  planned: [
    seedTask("t-chat-checklist", "Update the release checklist for 2.4", "", {
      space: LUMEN_SPACE,
      due_on: inDays(2),
      assignee: ME_PERSON,
      source: fromChat({ ...RELEASE, message: { url: `${MESSAGE_LINK}/8815`, sent_at: minutesAgo(68 * 60) } }),
    }),
  ],
  building: [
    seedTask("t-chat-invites", "Send the beta invite list to support", "", {
      status: "in_progress",
      space: LUMEN_SPACE,
      due_on: inDays(3),
      assignee: ME_PERSON,
      source: fromChat({ ...RELEASE, message: { url: `${MESSAGE_LINK}/8846`, sent_at: minutesAgo(44 * 60) } }),
    }),
  ],
});
