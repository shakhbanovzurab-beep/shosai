"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { supportApi } from "../api/support-api";
import type { AttachmentMeta, Conversation, MessageKind, UpdateConversationRequest } from "../domain/contract";
import { detailResource, listResource, type OutboxItem, patchRows, receive, useInbox } from "./support-store";

function setOutbox(conversationId: string, change: (items: OutboxItem[]) => OutboxItem[]) {
  useInbox.setState((s) => ({ outbox: { ...s.outbox, [conversationId]: change(s.outbox[conversationId] ?? []) } }));
}

async function deliver(conversationId: string, item: OutboxItem) {
  const update = (patch: Partial<OutboxItem>) =>
    setOutbox(conversationId, (items) => items.map((i) => (i.localId === item.localId ? { ...i, ...patch } : i)));
  try {
    const detail = await supportApi.send(conversationId, {
      body: item.body,
      kind: item.kind,
      attachments: item.attachments,
    });
    const sent = detail.messages.findLast((m) => m.author === "agent" && m.kind === item.kind);
    update({ status: "sent", serverId: sent?.id ?? null });
    receive(detail);
  } catch (error) {
    update({ status: "failed" });
    toast.error(item.kind === "note" ? "Не удалось сохранить заметку" : "Не удалось отправить ответ", {
      description: errorMessage(error),
    });
  }
}

/** Shows the message in the thread at once and sends it in the background. */
export function sendMessage(
  conversationId: string,
  message: { body: string; kind: MessageKind; attachments: AttachmentMeta[] },
) {
  const item: OutboxItem = {
    ...message,
    localId: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    status: "sending",
    serverId: null,
  };
  setOutbox(conversationId, (items) => [...items, item]);
  void deliver(conversationId, item);
}

export function retryMessage(conversationId: string, localId: string) {
  const item = useInbox.getState().outbox[conversationId]?.find((i) => i.localId === localId);
  if (!item) return;
  const retry = { ...item, status: "sending" as const };
  setOutbox(conversationId, (items) => items.map((i) => (i.localId === localId ? retry : i)));
  void deliver(conversationId, retry);
}

export function discardMessage(conversationId: string, localId: string) {
  setOutbox(conversationId, (items) => items.filter((i) => i.localId !== localId));
}

/** Applies a status, assignee or priority change straight away and rolls it back if the server refuses. */
export async function updateConversation(
  id: string,
  patch: UpdateConversationRequest,
  optimistic: Partial<Conversation>,
) {
  const resource = detailResource(id);
  const before = resource.getSnapshot();
  resource.update((data) => ({ ...data, ...optimistic }));
  patchRows(id, optimistic);
  try {
    receive(await supportApi.update(id, patch));
    const { filter, mine } = useInbox.getState();
    // A status or assignee change can move the row out of the current tab.
    void listResource(filter, mine).refresh();
  } catch (error) {
    if (before.status === "ready") receive(before.data);
    toast.error("Не удалось изменить разговор", { description: errorMessage(error) });
  }
}
