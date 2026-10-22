import type { ChatDigest, DigestItem, DigestPromise } from "@/features/chats/domain/digest-contract";
import { bodyOf, type Ctx, inWorkspace, json, refuse } from "@/features/chats/mocks/routes/http";
import { taskProposalsSchema } from "@/features/chats/mocks/routes/schemas";
import { digestOf, itemsOf, markProposed, markTask, releaseItems } from "@/features/chats/mocks/store/digests";
import { type ChatTaskDraft, createChatTasks } from "@/features/kanban/mocks/store/chat-tasks";
import { membership } from "@/features/workspace/mocks/demo-store";

import type { LeoProposal } from "../domain/proposals";
import { demoProposals, onDecision } from "./demo-proposals";

/*
 * «Сделать задачей» из дайджеста чата (CF-D5, AG-R2): агент без вызова модели кладёт в разговор одну карточку
 * `tasks.create` с задачей на каждый пункт. Одобрение создаёт задачи пространства с источником `chat`
 * (TK-D13) и отмечает пункты; отказ их освобождает. Тексты превью — демо: сервер собирает их из ключей i18n.
 */

const HOUR = 3_600_000;

const isPromise = (item: DigestItem): item is DigestPromise => "who" in item;
const busy = (item: DigestItem) =>
  item.task_id !== null || (item.proposal_id !== null && demoProposals.get(item.proposal_id)?.status === "proposed");

function draftOf(digest: ChatDigest, item: DigestItem): ChatTaskDraft {
  const { binding, messenger, title, id, workspace_id } = digest.chat;
  return {
    workspace_id,
    title: isPromise(item) ? item.text : item.text.slice(0, 200),
    due_on: isPromise(item) ? item.due_on : null,
    project_id: binding.kind === "project" ? binding.project.id : null,
    assignee_account: isPromise(item) ? item.who.user_id : null,
    chat: {
      connection_id: id,
      messenger,
      chat_title: title,
      message: { url: item.message.url, sent_at: item.message.sent_at },
    },
  };
}

function proposalOf(digest: ChatDigest, items: DigestItem[], space: string): LeoProposal {
  const where = digest.chat.binding.kind === "project" ? digest.chat.binding.project.name : space;
  return {
    id: `act-${crypto.randomUUID()}`,
    tool: "tasks.create",
    // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
    title: items.length === 1 ? `Create the task “${items[0].text}”` : `Create ${items.length} tasks in ${where}`,
    space,
    origin: { kind: "thread", app: null },
    reversibility: "reversible",
    warning: false,
    // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
    taint: `Prepared using messages from the chat “${digest.chat.title}”`,
    preview: {
      kind: "fields",
      fields: items.map((item, index) => ({
        // i18n-ignore: демо-данные; превью и источники сервер пишет на языке человека
        label: `Task ${index + 1}`,
        value: isPromise(item)
          ? [item.text, item.who.name, item.due_on ?? item.when_text].filter(Boolean).join(" · ")
          : item.text,
      })),
      body: null,
    },
    status: "proposed",
    outcome: null,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + HOUR).toISOString(),
    resolved_at: null,
  };
}

/** /v1/workspaces/[id]/chats/[chatId]/digests/[digestId]/task-proposals */
export const digestTaskProposalsRoute = {
  async POST(request: Request, { params }: Ctx<"id" | "chatId" | "digestId">) {
    const { chatId, digestId } = await params;
    return inWorkspace(params, "member", async (ws) => {
      const digest = digestOf(ws, chatId, digestId);
      if (!digest.ok) return refuse(digest.code);
      const body = await bodyOf(request, taskProposalsSchema);
      if ("refusal" in body) return body.refusal;
      const items = itemsOf(digest.value, body.data.item_ids);
      if (!items.ok) return refuse(items.code);
      if (items.value.some(busy)) return refuse("item_already_proposed");
      const proposal = proposalOf(digest.value, items.value, membership(ws)?.data.workspace.name ?? "");
      demoProposals.set(proposal.id, proposal);
      markProposed(items.value, proposal.id);
      onDecision(proposal.id, (approve) => {
        if (!approve) {
          releaseItems(items.value);
          return null;
        }
        const ids = createChatTasks(items.value.map((item) => draftOf(digest.value, item)));
        items.value.forEach((item, index) => {
          const id = ids[index];
          if (id) markTask(item, id);
        });
        // i18n-ignore: демо-данные; итог сервер пишет на языке человека
        return `Created ${ids.filter(Boolean).length} of ${ids.length}`;
      });
      return json(proposal, 201);
    });
  },
};
