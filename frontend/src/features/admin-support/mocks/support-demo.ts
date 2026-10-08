import type {
  AttachmentMeta,
  Conversation,
  ConversationDetail,
  ConversationsResponse,
  MessageKind,
  StatusFilter,
  UpdateConversationRequest,
} from "../domain/contract";
import { PRIORITY_LABELS, STATUS_LABELS } from "../domain/labels";
import { type ConversationRecord, ME, msg, now, TEAMMATES, teammate, userById } from "./demo-people";
import { CANNED, LIVE_REPLIES } from "./demo-replies";
import { seedActive } from "./demo-seed-active";
import { seedHistory } from "./demo-seed-history";

/*
 * In-memory stand-in for the admin support inbox, used when BACKEND_API_URL is unset; resets on restart.
 * To feel live, every so often (driven by the client's polling) a user answers an open conversation,
 * and agent replies get marked read a little after they are sent.
 */

type DemoState = {
  conversations: Map<string, ConversationRecord>;
  lastLiveAt: number;
  nextGap: number;
  replyIndex: number;
};

const shared = globalThis as typeof globalThis & { adminSupportDemo?: DemoState };
shared.adminSupportDemo ??= {
  conversations: new Map([...seedActive(), ...seedHistory()].map((c) => [c.id, c])),
  lastLiveAt: Date.now(),
  nextGap: 30_000,
  replyIndex: 0,
};
const state = shared.adminSupportDemo;

/* ---------- Live simulation, advanced on each read ---------- */

const READ_AFTER_MS = 12_000;

function tick() {
  const time = Date.now();
  // Users read agent replies a little after they are sent.
  for (const c of state.conversations.values()) {
    for (const m of c.messages) {
      if (m.author === "agent" && m.kind === "reply" && m.read_at === null && c.status !== "resolved") {
        if (time - Date.parse(m.created_at) > READ_AFTER_MS) m.read_at = now();
      }
    }
  }
  if (time - state.lastLiveAt < state.nextGap) return;
  state.lastLiveAt = time;
  state.nextGap = 25_000 + Math.floor(Math.random() * 25_000);

  // Prefer a conversation where we spoke last, so the user's answer reads naturally.
  const active = [...state.conversations.values()].filter((c) => c.status !== "resolved");
  const answered = active.filter((c) => c.messages.findLast((m) => m.kind === "reply")?.author === "agent");
  const pool = answered.length > 0 ? answered : active;
  const target = pool[Math.floor(Math.random() * pool.length)];
  if (!target) return;
  const reply = LIVE_REPLIES[state.replyIndex % LIVE_REPLIES.length];
  state.replyIndex += 1;
  target.messages.push(
    msg({
      author: "user",
      author_name: userById(target.user_id).name,
      created_at: now(),
      body: reply.body,
      attachments: reply.attachments ?? [],
    }),
  );
  target.status = "open";
  target.unread_count += 1;
  target.updated_at = now();
}

/* ---------- Shaping ---------- */

function toConversation(c: ConversationRecord): Conversation {
  const { user_id, assignee_id, messages, ...rest } = c;
  const user = userById(user_id);
  const last = messages.findLast((m) => m.author !== "system") ?? messages[messages.length - 1];
  return {
    ...rest,
    user: { id: user.id, name: user.name, email: user.email, avatar_url: user.avatar_url },
    assignee: assignee_id ? teammate(assignee_id) : null,
    last_message: { author: last.author, kind: last.kind, body: last.body, created_at: last.created_at },
  };
}

const byUpdated = (a: ConversationRecord, b: ConversationRecord) => b.updated_at.localeCompare(a.updated_at);

function toDetail(c: ConversationRecord): ConversationDetail {
  const past = [...state.conversations.values()]
    .filter((other) => other.user_id === c.user_id && other.id !== c.id)
    .toSorted(byUpdated)
    .map(({ id, number, subject, status, updated_at }) => ({ id, number, subject, status, updated_at }));
  return {
    ...toConversation(c),
    messages: c.messages.map((m) => ({ ...m })),
    profile: userById(c.user_id),
    past_conversations: past,
  };
}

/* ---------- API ---------- */

export function listConversations(filter: StatusFilter, mine: boolean): ConversationsResponse {
  tick();
  const scoped = [...state.conversations.values()].filter((c) => !mine || c.assignee_id === ME.id);
  const counts: Record<StatusFilter, number> = { open: 0, pending: 0, resolved: 0, all: scoped.length };
  for (const c of scoped) counts[c.status] += 1;
  const conversations = scoped
    .filter((c) => filter === "all" || c.status === filter)
    .toSorted(byUpdated)
    .map(toConversation);
  return { conversations, counts, me: ME, teammates: TEAMMATES };
}

/** Opening a conversation marks the user's messages as read. */
export function getConversation(id: string): ConversationDetail | null {
  tick();
  const c = state.conversations.get(id);
  if (!c) return null;
  c.unread_count = 0;
  return toDetail(c);
}

export function addMessage(
  id: string,
  body: string,
  kind: MessageKind,
  attachments: AttachmentMeta[],
): ConversationDetail | null {
  const c = state.conversations.get(id);
  if (!c) return null;
  c.messages.push(
    msg({
      author: "agent",
      kind,
      author_name: ME.name,
      created_at: now(),
      body,
      attachments: attachments.map((a) => ({ ...a, url: null })),
    }),
  );
  c.unread_count = 0;
  c.updated_at = now();
  return toDetail(c);
}

export type UpdateResult = { ok: true; detail: ConversationDetail } | { ok: false; status: 404 | 422; message: string };

export function updateConversation(id: string, patch: UpdateConversationRequest): UpdateResult {
  const c = state.conversations.get(id);
  if (!c) return { ok: false, status: 404, message: "Разговор не найден." };
  const events: string[] = [];
  if (patch.assignee !== undefined && patch.assignee !== c.assignee_id) {
    const next = patch.assignee === null ? null : teammate(patch.assignee);
    if (patch.assignee !== null && !next) return { ok: false, status: 422, message: "Нет такого сотрудника." };
    c.assignee_id = next?.id ?? null;
    events.push(next ? `Назначено: ${next.name}` : "Назначение снято");
  }
  if (patch.status && patch.status !== c.status) {
    c.status = patch.status;
    events.push(`Статус изменён: ${STATUS_LABELS[patch.status]}`);
  }
  if (patch.priority && patch.priority !== c.priority) {
    c.priority = patch.priority;
    events.push(`Приоритет: ${PRIORITY_LABELS[patch.priority]}`);
  }
  for (const body of events)
    c.messages.push(msg({ author: "system", created_at: now(), body: `${body} · ${ME.name}` }));
  if (events.length > 0) c.updated_at = now();
  return { ok: true, detail: toDetail(c) };
}

export const listCannedReplies = () => CANNED;
