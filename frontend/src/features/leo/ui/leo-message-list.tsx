"use client";

import { ArrowDown, History, RotateCcw } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";
import { Spinner } from "@/components/ui/spinner";

import type { LeoProposal } from "../domain/proposals";
import type { LeoSource } from "../domain/sources";
import type { LeoMessage } from "../domain/types";
import type { LeoChat } from "../model/leo-chat";
import { CitedAnswer } from "./cited/cited-answer";
import { LeoArtifacts } from "./leo-artifacts";
import { CopyAction, MessageAction } from "./leo-message-actions";
import { RatingActions } from "./leo-rating";
import { LeoReplyError } from "./leo-reply-error";
import { LeoSteps } from "./leo-steps";
import { LeoUserMessage } from "./leo-user-message";
import { LeoMarkdown } from "./markdown/leo-markdown";
import { LeoProposalCard } from "./proposal/leo-proposal";

interface LeoMessageListProps {
  readonly messages: LeoMessage[];
  readonly isBusy: boolean;
  /** Более ранние сообщения треда на сервере: кнопка над разговором их подгружает. */
  readonly earlier?: LeoChat["earlier"];
  readonly onRegenerate: () => void;
  readonly onEditLast: (content: string) => void;
  /** Карточка одобрения, сделанная из артефакта ответа (дайджест чата), — в этот же ответ. */
  readonly onProposal: (messageId: string, proposal: LeoProposal) => void;
}

export function LeoMessageList({
  messages,
  isBusy,
  earlier,
  onRegenerate,
  onEditLast,
  onProposal,
}: LeoMessageListProps) {
  const t = useTranslations("leo");
  const lastAssistantId = messages.findLast((m) => m.role === "assistant")?.id;
  const lastUserId = messages.findLast((m) => m.role === "user")?.id;

  return (
    <MessageScrollerProvider autoScroll>
      <MessageScroller className="min-h-0 flex-1">
        <MessageScrollerViewport>
          <MessageScrollerContent className="gap-6 px-4 py-5 group-data-[expanded=true]/leo:mx-auto group-data-[expanded=true]/leo:w-full group-data-[expanded=true]/leo:max-w-3xl">
            {earlier?.available ? (
              <Button
                variant="ghost"
                size="sm"
                className="self-center"
                disabled={earlier.loading}
                onClick={earlier.load}
              >
                {earlier.loading ? <Spinner data-icon="inline-start" /> : <History data-icon="inline-start" />}
                {t("message.earlier")}
              </Button>
            ) : null}
            {messages.map((message) => (
              <MessageScrollerItem key={message.id} messageId={message.id} scrollAnchor={message.role === "user"}>
                {message.role === "user" ? (
                  <LeoUserMessage
                    message={message}
                    canEdit={message.id === lastUserId && !isBusy}
                    onEdit={onEditLast}
                  />
                ) : (
                  <AssistantMessage
                    message={message}
                    isLast={message.id === lastAssistantId}
                    canRegenerate={!isBusy}
                    onRegenerate={onRegenerate}
                    onProposal={(proposal) => onProposal(message.id, proposal)}
                  />
                )}
              </MessageScrollerItem>
            ))}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton>
          <ArrowDown />
          <span className="sr-only">{t("message.latest")}</span>
        </MessageScrollerButton>
      </MessageScroller>
    </MessageScrollerProvider>
  );
}

interface AssistantMessageProps {
  readonly message: LeoMessage;
  readonly isLast: boolean;
  readonly canRegenerate: boolean;
  readonly onRegenerate: () => void;
}

function AssistantMessage({
  message,
  isLast,
  canRegenerate,
  onRegenerate,
  onProposal,
}: AssistantMessageProps & { readonly onProposal: (proposal: LeoProposal) => void }) {
  const isStreaming = message.status === "streaming";
  const hasAnswer = message.content.length > 0;
  const artifacts = message.artifacts ?? [];
  const proposals = message.proposals ?? [];
  const showActions = !isStreaming && (hasAnswer || isLast);

  return (
    <div className="flex flex-col gap-3">
      <LeoSteps message={message} />
      {message.status === "error" ? <LeoReplyError failure={message.failure} /> : null}
      {hasAnswer || showActions || artifacts.length > 0 || proposals.length > 0 ? (
        <div className="flex flex-col gap-1">
          {hasAnswer ? <AnswerCard text={message.content} sources={message.sources} isStreaming={isStreaming} /> : null}
          {artifacts.length > 0 ? <LeoArtifacts artifacts={artifacts} onProposal={onProposal} /> : null}
          {proposals.map((proposal) => (
            <LeoProposalCard key={proposal.id} proposal={proposal} />
          ))}
          {showActions ? (
            <AnswerActions
              message={message}
              isLast={isLast}
              canRegenerate={canRegenerate}
              onRegenerate={onRegenerate}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function AnswerCard({ text, sources, isStreaming }: { text: string; sources?: LeoSource[]; isStreaming: boolean }) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-3 text-sm leading-relaxed">
      {sources?.length ? (
        <CitedAnswer text={text} sources={sources} isStreaming={isStreaming} />
      ) : (
        <LeoMarkdown text={text} />
      )}
      {isStreaming ? (
        <span
          className="ms-0.5 inline-block h-4 w-1.5 animate-pulse rounded-full bg-foreground align-middle"
          aria-hidden="true"
        />
      ) : null}
    </div>
  );
}

function AnswerActions({ message, isLast, canRegenerate, onRegenerate }: AssistantMessageProps) {
  const t = useTranslations("leo");
  return (
    <div className="flex flex-wrap items-center gap-0.5 ps-2">
      {message.content ? <CopyAction text={message.content} /> : null}
      {message.feedback !== undefined && message.status === "done" ? (
        <RatingActions messageId={message.id} saved={message.feedback} />
      ) : null}
      {isLast ? (
        <MessageAction onClick={onRegenerate} disabled={!canRegenerate}>
          <RotateCcw />
          {message.status === "error" ? t("message.tryAgain") : t("message.regenerate")}
        </MessageAction>
      ) : null}
    </div>
  );
}
