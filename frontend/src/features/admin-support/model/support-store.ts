"use client";

import { create } from "zustand";

import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { supportApi } from "../api/support-api";
import type {
  AttachmentMeta,
  Conversation,
  ConversationDetail,
  ConversationsResponse,
  MessageKind,
  StatusFilter,
} from "../domain/contract";

/* ---------- Server resources, polled every 5 s while on screen ---------- */

const POLL_MS = 5000;

/** Adds a steady refresh to a resource while anyone is subscribed and the tab is visible. */
function withInterval<T>(resource: PollingResource<T>): PollingResource<T> {
  let timer: ReturnType<typeof setInterval> | undefined;
  let subscribers = 0;
  return {
    ...resource,
    subscribe(listener) {
      const unsubscribe = resource.subscribe(listener);
      subscribers += 1;
      if (subscribers === 1) {
        timer = setInterval(() => {
          if (document.visibilityState === "visible") void resource.refresh();
        }, POLL_MS);
      }
      return () => {
        unsubscribe();
        subscribers -= 1;
        if (subscribers === 0) clearInterval(timer);
      };
    },
  };
}

const listResources = new Map<string, PollingResource<ConversationsResponse>>();
const detailResources = new Map<string, PollingResource<ConversationDetail>>();

/** The conversation list for one tab; cached, so switching back shows the last data at once. */
export function listResource(filter: StatusFilter, mine: boolean) {
  const key = `${filter}:${mine}`;
  let resource = listResources.get(key);
  if (!resource) {
    resource = withInterval(createPollingResource(() => supportApi.list(filter, mine)));
    listResources.set(key, resource);
  }
  return resource;
}

export function detailResource(id: string) {
  let resource = detailResources.get(id);
  if (!resource) {
    resource = withInterval(createPollingResource(() => supportApi.get(id)));
    detailResources.set(id, resource);
  }
  return resource;
}

export const cannedRepliesResource = createPollingResource(supportApi.cannedReplies);

/* ---------- Inbox UI state ---------- */

export type OutboxItem = {
  localId: string;
  body: string;
  kind: MessageKind;
  attachments: AttachmentMeta[];
  created_at: string;
  status: "sending" | "failed" | "sent";
  /** The server's id once sent; the item hides when the thread contains it. */
  serverId: string | null;
};

export type Draft = { body: string; kind: MessageKind };
const EMPTY_DRAFT: Draft = { body: "", kind: "reply" };

type InboxState = {
  filter: StatusFilter;
  mine: boolean;
  selectedId: string | null;
  /** The user profile sheet on screens without the third column. */
  profileOpen: boolean;
  drafts: Record<string, Draft>;
  outbox: Record<string, OutboxItem[]>;
  setFilter: (filter: StatusFilter) => void;
  setMine: (mine: boolean) => void;
  select: (id: string | null) => void;
  setProfileOpen: (open: boolean) => void;
  setDraft: (id: string, draft: Partial<Draft>) => void;
};

export const useInbox = create<InboxState>((set) => ({
  filter: "open",
  mine: false,
  selectedId: null,
  profileOpen: false,
  drafts: {},
  outbox: {},
  setFilter: (filter) => set({ filter }),
  setMine: (mine) => set({ mine }),
  select: (id) => {
    set({ selectedId: id, profileOpen: false });
    if (id) patchRows(id, { unread_count: 0 });
  },
  setProfileOpen: (profileOpen) => set({ profileOpen }),
  setDraft: (id, draft) =>
    set((s) => ({ drafts: { ...s.drafts, [id]: { ...(s.drafts[id] ?? EMPTY_DRAFT), ...draft } } })),
}));

export const useDraft = (id: string) => useInbox((s) => s.drafts[id] ?? EMPTY_DRAFT);

/* ---------- Keeping the list in step with the open conversation ---------- */

export function patchRows(id: string, change: Partial<Conversation>) {
  for (const resource of listResources.values()) {
    resource.update((data) => ({
      ...data,
      conversations: data.conversations.map((c) => (c.id === id ? { ...c, ...change } : c)),
    }));
  }
}

function toRow({ messages: _messages, profile: _profile, past_conversations: _past, ...row }: ConversationDetail) {
  return row satisfies Conversation;
}

export function receive(detail: ConversationDetail) {
  detailResources.get(detail.id)?.update(() => detail);
  patchRows(detail.id, toRow(detail));
}
