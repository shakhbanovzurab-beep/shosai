import {
  type ChatDigest,
  DIGEST_ITEMS_PER_PROPOSAL,
  type DigestItem,
  type DigestSection,
  digestItems,
  startsBeforeHistory,
} from "./digest-contract";

/*
 * Как показывать дайджест (план CHATS-frontend §3.8): что с пунктом и задачей из него, какие оговорки о
 * покрытии нужны, сколько пунктов видно до «Показать все» и что сказать, если отмечать нечего.
 */

export const SECTION_PREVIEW = 5;
export const DIGEST_SECTIONS: readonly DigestSection[] = ["decisions", "questions", "promises"];

export type ItemTask =
  | { kind: "free" }
  | { kind: "making" }
  | { kind: "waiting"; proposalId: string }
  | { kind: "created"; taskId: string };

/** Задача из пункта: создана, ждёт одобрения карточки, готовится сейчас или пункт свободен. */
export function itemTask(item: DigestItem, making: ReadonlySet<string>): ItemTask {
  if (item.task_id) return { kind: "created", taskId: item.task_id };
  if (item.proposal_id) return { kind: "waiting", proposalId: item.proposal_id };
  return making.has(item.id) ? { kind: "making" } : { kind: "free" };
}

const isFree = (item: DigestItem) => item.task_id === null && item.proposal_id === null;

/** Обещания, которые ещё можно сделать задачами, — не больше, чем помещается в одну карточку. */
export const freePromises = (digest: Pick<ChatDigest, "promises">) =>
  digest.promises.filter(isFree).slice(0, DIGEST_ITEMS_PER_PROPOSAL);

export type CoverageNote = { kind: "history"; from: string } | { kind: "truncated" };

/** Оговорки: период начался до того, как у Shosai появились сообщения чата, или прочитаны не все. */
export function coverageNotes(digest: Pick<ChatDigest, "period" | "coverage">): CoverageNote[] {
  const notes: CoverageNote[] = [];
  if (startsBeforeHistory(digest)) notes.push({ kind: "history", from: digest.coverage.history_from });
  if (digest.coverage.truncated) notes.push({ kind: "truncated" });
  return notes;
}

/** Сообщений за период не было, отмечать нечего — или есть что показать. */
export function digestContent(digest: ChatDigest): "no_messages" | "nothing_found" | "items" {
  if (digest.coverage.messages_read === 0) return "no_messages";
  return digestItems(digest).length === 0 ? "nothing_found" : "items";
}

/** Начало охваченного периода: не раньше, чем у Shosai есть сообщения. */
export const coveredFrom = (digest: Pick<ChatDigest, "period" | "coverage">) =>
  startsBeforeHistory(digest) ? digest.coverage.history_from : digest.period.from;
