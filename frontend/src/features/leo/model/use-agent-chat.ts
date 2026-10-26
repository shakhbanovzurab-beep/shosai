import * as React from "react";

import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { useUiLanguage } from "@/hooks/use-ui-language";
import { useRouter } from "@/lib/navigation";

import { agentApi, type TurnBody } from "../api/agent-api";
import { lastQuestion } from "../domain/agent-history";
import { contextKey, type LeoContext } from "../domain/context";
import { withEpilogues } from "../domain/epilogues";
import { isRecorded, type LiveTurn, mergedConversation, type TurnKind } from "../domain/live-turns";
import { pageSubject } from "../domain/page-subject";
import type { LeoMessage } from "../domain/types";
import { chooseThread, messagesKey, scopeOf, threadsKey, useAgentThread } from "./agent-thread";
import { refusal, runTurn, stopTurn } from "./agent-turn-runner";
import { addTurn, dropTurns, failedReply, liveTurns, subscribeTurns, updateTurn } from "./agent-turns";
import { uploadedAttachments } from "./agent-uploads";
import { liveEpilogues, subscribeEpilogues } from "./epilogues";
import type { LeoChat } from "./leo-chat";
import { useAgentThreads } from "./use-agent-threads";
import { useSettledEpilogues } from "./use-settled-epilogues";

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
  const epilogues = React.useSyncExternalStore(subscribeEpilogues, liveEpilogues, liveEpilogues);
  const asking = turns.some((turn) => turn.reply.status === "streaming");
  const thread = useAgentThread(scopeKey, scope, !asking);
  const threads = useAgentThreads(scopeKey, scope, thread.threadId);
  const visible = turns.filter((turn) => turn.threadId === thread.threadId || turn.threadId === null);
  // Эпилог после одобрения идёт в своём треде: пока он пишет, новый вопрос ждёт, а «Стоп» останавливает его.
  const shown = epilogues.filter((epilogue) => epilogue.threadId !== null && epilogue.threadId === thread.threadId);
  const writing = shown.find((epilogue) => epilogue.reply?.status === "streaming");
  const isBusy = asking || writing !== undefined;
  const messages = withEpilogues(mergedConversation(thread.conversation, visible), shown);
  useSettledEpilogues(epilogues);

  // Записанный историей ход больше не нужен: его ответ уже в ней.
  React.useEffect(() => {
    dropTurns(scopeKey, (turn) => isRecorded(turn, thread.conversation));
  }, [scopeKey, thread.conversation]);

  const ask = async (
    kind: TurnKind,
    question: LeoMessage,
    body: TurnBody,
    files: readonly File[] = [],
  ): Promise<LeoMessage | undefined> => {
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
    if (files.length > 0) {
      try {
        body.upload_ids = await uploadedAttachments(files);
      } catch (error) {
        console.warn("Leo: файлы вопроса не загрузились", error);
        updateTurn(scopeKey, key, (live) => ({ ...live, reply: failedReply(live.reply, "upload_failed") }));
        return turnOfKey(key)?.reply;
      }
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

  const send = (content: string, files: File[] = []): Promise<LeoMessage | undefined> => {
    if (isBusy) return Promise.resolve(undefined);
    const attachments = files.map((file) => ({
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      type: file.type,
    }));
    const question: LeoMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      status: "done",
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    return ask("new", question, { ...base(), text: content }, files);
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
    let stopping: Promise<void> | undefined;
    if (running) stopping = stopTurn(scopeKey, running.key);
    else if (writing) stopping = agentApi.cancel(writing.runId);
    stopping?.catch(() => toast.error(t("failure.stopFailed")));
  };

  const reset = () => {
    dropTurns(scopeKey, (turn) => turn.reply.status !== "streaming");
    chooseThread(scopeKey, null);
  };

  // Карточку из пунктов дайджеста сервер кладёт в тот же ответ (AG-R2): история перечитывается и показывает её.
  const addProposal = () => void queryClient.invalidateQueries({ queryKey: messagesKey(thread.threadId) });

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
    attachments: true,
    threads,
  };
}
