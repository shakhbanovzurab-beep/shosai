import * as React from "react";

import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { useUiLanguage } from "@/hooks/use-ui-language";
import { useRouter } from "@/lib/navigation";

import { agentApi, type TurnBody } from "../api/agent-api";
import { lastQuestion } from "../domain/agent-history";
import { contextKey, type LeoContext } from "../domain/context";
import { isRecorded, type LiveTurn, mergedConversation, type TurnKind } from "../domain/live-turns";
import { pageSubject } from "../domain/page-subject";
import type { LeoProposal } from "../domain/proposals";
import type { LeoMessage } from "../domain/types";
import { chooseThread, messagesKey, scopeOf, threadsKey, useAgentThread } from "./agent-thread";
import { refusal, runTurn, stopTurn } from "./agent-turn-runner";
import { addTurn, dropTurns, failedReply, liveTurns, subscribeTurns, updateTurn } from "./agent-turns";
import type { LeoChat } from "./leo-chat";
import { useAgentThreads } from "./use-agent-threads";

/** Leo на настоящем API (`/v1/agent/*`): разговор пространства, его ходы, «Стоп», «Ещё раз» и правка. */
export function useAgentChat({ page, context }: { page: string; context: LeoContext }): LeoChat {
  const scopeKey = contextKey(context);
  const scope = scopeOf(context);
  const locale = useUiLanguage();
  const router = useRouter();
  const queryClient = useQueryClient();
  const t = useTranslations("leo");
  const turns = React.useSyncExternalStore(
    subscribeTurns,
    () => liveTurns(scopeKey),
    () => liveTurns(scopeKey),
  );
  const isBusy = turns.some((turn) => turn.reply.status === "streaming");
  const thread = useAgentThread(scopeKey, scope, !isBusy);
  const threads = useAgentThreads(scopeKey, scope, thread.threadId);
  const visible = turns.filter((turn) => turn.threadId === thread.threadId || turn.threadId === null);
  const messages = mergedConversation(thread.conversation, visible);

  // Записанный историей ход больше не нужен: его ответ уже в ней.
  React.useEffect(() => {
    dropTurns(scopeKey, (turn) => isRecorded(turn, thread.conversation));
  }, [scopeKey, thread.conversation]);

  const ask = async (kind: TurnKind, question: LeoMessage, body: TurnBody): Promise<LeoMessage | undefined> => {
    const key = crypto.randomUUID();
    const reply: LeoMessage = { id: `${key}:reply`, role: "assistant", content: "", status: "streaming", steps: [] };
    const turn: LiveTurn = {
      key,
      kind,
      threadId: thread.threadId,
      question,
      reply,
      runId: null,
      seq: 0,
      startedAt: Date.now(),
    };
    addTurn(scopeKey, turn);
    let threadId = thread.threadId;
    if (threadId === null) {
      try {
        threadId = (await agentApi.createThread(scope, `${key}:thread`)).id;
      } catch (error) {
        updateTurn(scopeKey, key, (live) => ({ ...live, reply: failedReply(live.reply, ...refusal(error)) }));
        return turnOfKey(key)?.reply;
      }
      const created = threadId;
      updateTurn(scopeKey, key, (live) => ({ ...live, threadId: created }));
      chooseThread(scopeKey, created);
    }
    const settledThread = threadId;
    return runTurn({
      scope: scopeKey,
      key,
      threadId,
      body,
      onNavigate: (path) => router.push(path),
      onSettled: () => {
        void queryClient.invalidateQueries({ queryKey: messagesKey(settledThread) });
        void queryClient.invalidateQueries({ queryKey: threadsKey(scopeKey) });
      },
    });
  };

  const turnOfKey = (key: string) => liveTurns(scopeKey).find((turn) => turn.key === key);
  // Строка запроса читается в момент вопроса: фильтры страницы в адресе не перерисовывают Leo.
  const base = () => {
    const surface = { path: page, subject: pageSubject(page, window.location.search) };
    return { locale, surface, supersede: false };
  };

  const send = (content: string): Promise<LeoMessage | undefined> => {
    if (isBusy) return Promise.resolve(undefined);
    const question: LeoMessage = { id: crypto.randomUUID(), role: "user", content, status: "done" };
    return ask("new", question, { ...base(), text: content });
  };

  const again = (kind: Exclude<TurnKind, "new">, content?: string) => {
    const last = lastQuestion(messages);
    if (isBusy || last === undefined) return;
    const text = content ?? last.content;
    const question: LeoMessage = { ...last, content: text };
    const replaces = kind === "edit" ? { edit_of: last.id } : { regenerate_of: last.id };
    void ask(kind, question, { ...base(), text, ...replaces });
  };

  const stop = () => {
    const running = turns.find((turn) => turn.reply.status === "streaming");
    if (running === undefined) return;
    stopTurn(scopeKey, running.key).catch(() => toast.error(t("failure.stopFailed")));
  };

  const reset = () => {
    dropTurns(scopeKey, (turn) => turn.reply.status !== "streaming");
    chooseThread(scopeKey, null);
  };

  // Карточки из артефактов ответа приходят с шагом 9b; до него в ответах Leo на API их нет.
  const addProposal = (_messageId: string, _proposal: LeoProposal) => undefined;

  return {
    messages,
    isBusy,
    loading: thread.loading,
    send,
    stop,
    regenerate: () => again("regenerate"),
    editLast: (content: string) => again("edit", content),
    addProposal,
    reset,
    earlier: thread.earlier,
    attachments: false,
    threads,
  };
}
