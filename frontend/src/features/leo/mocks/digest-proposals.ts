import type { ChatDigest, DigestItem, DigestPromise } from "@/features/chats/domain/digest-contract";
import { bodyOf, type Ctx, inWorkspace, json, refuse } from "@/features/chats/mocks/routes/http";
import { taskProposalsSchema } from "@/features/chats/mocks/routes/schemas";
import { digestOf, itemsOf, markProposed } from "@/features/chats/mocks/store/digests";
import { membership } from "@/features/workspace/mocks/demo-store";

import type { LeoProposal } from "../domain/proposals";

/*
 * «Сделать задачей» из дайджеста чата (CF-D5, AG-R2): агент без вызова модели кладёт в разговор одну карточку
 * `tasks.create` с задачей на каждый пункт, и пункты заняты ею. Решают её уже на `/v1/agent/actions*` — у них моков
 * нет (шаг 10): срез chats уходит с моков вместе с этим путём. Тексты превью — демо: сервер собирает их из ключей i18n.
 */

const HOUR = 3_600_000;

const isPromise = (item: DigestItem): item is DigestPromise => "who" in item;
const busy = (item: DigestItem) => item.task_id !== null || item.proposal_id !== null;

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
    nonce: crypto.randomUUID(),
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
      markProposed(items.value, proposal.id);
      return json(proposal, 201);
    });
  },
};
