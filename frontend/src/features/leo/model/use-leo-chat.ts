"use client";

import * as React from "react";

import { useUiLanguage } from "@/hooks/use-ui-language";

import { streamReply } from "../api/leo-api";
import { contextKey, type LeoContext } from "../domain/context";
import { applyEvent, finishMessage } from "../domain/messages";
import type { LeoAttachment, LeoMessage } from "../domain/types";
import {
  attachmentFiles,
  createId,
  getMessages,
  getServerMessages,
  setMessages,
  subscribe,
  updateMessage,
} from "./chat-store";

/** The conversation of one context; switching context switches conversation, the other stays as it was. */
export function useLeoChat({ page, context }: { page: string; context: LeoContext }) {
  const key = contextKey(context);
  const locale = useUiLanguage();
  const read = React.useCallback(() => getMessages(key), [key]);
  const messages = React.useSyncExternalStore(subscribe, read, getServerMessages);
  const abortRef = React.useRef<AbortController | null>(null);

  const isBusy = messages.some((m) => m.status === "streaming");

  React.useEffect(() => () => abortRef.current?.abort(), []);

  // Resolves with Leo's finished reply (done, stopped or failed) once the stream is over.
  const requestReply = React.useCallback(
    (history: LeoMessage[]): Promise<LeoMessage | undefined> => {
      const replyId = createId();
      setMessages(key, () => [
        ...history,
        { id: replyId, role: "assistant", content: "", status: "streaming", steps: [] },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      const lastMessage = history[history.length - 1];
      return streamReply({
        page,
        locale,
        context,
        history,
        files: attachmentFiles.get(lastMessage.id) ?? [],
        signal: controller.signal,
        onEvent: (event) => updateMessage(key, replyId, (m) => applyEvent(m, event)),
      }).then((status) => {
        // Covers an aborted or failed request, and a stream that ended without a final event.
        updateMessage(key, replyId, (m) => (m.status === "streaming" ? finishMessage(m, status ?? "error") : m));
        if (abortRef.current === controller) abortRef.current = null;
        return getMessages(key).find((m) => m.id === replyId);
      });
    },
    [page, locale, context, key],
  );

  const send = React.useCallback(
    (content: string, files: File[] = []): Promise<LeoMessage | undefined> => {
      if (isBusy) return Promise.resolve(undefined);
      const id = createId();
      const attachments = files.map(
        (file): LeoAttachment => ({ id: createId(), name: file.name, size: file.size, type: file.type }),
      );
      if (files.length > 0) attachmentFiles.set(id, files);
      return requestReply([
        ...messages,
        { id, role: "user", content, status: "done", attachments: attachments.length ? attachments : undefined },
      ]);
    },
    [isBusy, messages, requestReply],
  );

  const stop = React.useCallback(() => abortRef.current?.abort(), []);

  const regenerate = React.useCallback(() => {
    if (isBusy) return;
    const lastUserIndex = messages.findLastIndex((m) => m.role === "user");
    if (lastUserIndex === -1) return;
    void requestReply(messages.slice(0, lastUserIndex + 1));
  }, [isBusy, messages, requestReply]);

  // Rewrites the last user message and asks again; the earlier reply is replaced. Attachments are kept.
  const editLast = React.useCallback(
    (content: string) => {
      if (isBusy) return;
      const lastUserIndex = messages.findLastIndex((m) => m.role === "user");
      if (lastUserIndex === -1) return;
      const edited = { ...messages[lastUserIndex], content };
      void requestReply([...messages.slice(0, lastUserIndex), edited]);
    },
    [isBusy, messages, requestReply],
  );

  const reset = React.useCallback(() => {
    abortRef.current?.abort();
    attachmentFiles.clear();
    setMessages(key, () => []);
  }, [key]);

  return { messages, isBusy, send, stop, regenerate, editLast, reset };
}
