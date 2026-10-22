import { type ChatDigest, type DigestItem, digestItems } from "../../domain/digest-contract";
import { fail, type Outcome, ok } from "./outcome";
import { demo } from "./state";

/*
 * Дайджесты чатов: читает их тот, кто просил (в демо — сам пользователь); отключение чата стирает их.
 * Карточку одобрения из пунктов делает агент (моки leo), а сюда записывает, какие пункты он взял и какие
 * задачи создал.
 */

export function digestOf(workspaceId: string, chatId: string, digestId: string): Outcome<ChatDigest> {
  const digest = demo().digests.get(digestId);
  if (!digest || digest.chat.id !== chatId || digest.chat.workspace_id !== workspaceId) return fail("digest_not_found");
  return ok(digest);
}

export function eraseDigestsOf(chatId: string) {
  const digests = demo().digests;
  for (const [id, digest] of digests) if (digest.chat.id === chatId) digests.delete(id);
}

/** Пункты по ид, все или ни одного. */
export function itemsOf(digest: ChatDigest, ids: readonly string[]): Outcome<DigestItem[]> {
  const byId = new Map(digestItems(digest).map((item) => [item.id, item]));
  const items = ids.map((id) => byId.get(id));
  return items.every((item) => item !== undefined) ? ok(items) : fail("item_not_found");
}

export function markProposed(items: readonly DigestItem[], proposalId: string) {
  for (const item of items) item.proposal_id = proposalId;
}

/** Карточку отклонили или она истекла: пункты снова свободны. */
export function releaseItems(items: readonly DigestItem[]) {
  for (const item of items) item.proposal_id = null;
}

export function markTask(item: DigestItem, taskId: string) {
  item.task_id = taskId;
}
