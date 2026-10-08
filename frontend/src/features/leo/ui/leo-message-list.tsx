"use client";

import { RotateCcw } from "lucide-react";
import { useTranslations } from "use-intl";

import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";

import type { LeoMessage } from "../domain/types";
import { CopyAction, MessageAction } from "./leo-message-actions";
import { LeoRichText } from "./leo-rich-text";
import { LeoSteps } from "./leo-steps";
import { LeoUserMessage } from "./leo-user-message";

interface LeoMessageListProps {
  readonly messages: LeoMessage[];
  readonly isBusy: boolean;
  readonly onRegenerate: () => void;
  readonly onEditLast: (content: string) => void;
}

export function LeoMessageList({ messages, isBusy, onRegenerate, onEditLast }: LeoMessageListProps) {
  const lastAssistantId = messages.findLast((m) => m.role === "assistant")?.id;
  const lastUserId = messages.findLast((m) => m.role === "user")?.id;

  return (
    <MessageScrollerProvider autoScroll>
      <MessageScroller className="min-h-0 flex-1">
        <MessageScrollerViewport>
          <MessageScrollerContent className="gap-6 px-4 py-5 group-data-[expanded=true]/leo:mx-auto group-data-[expanded=true]/leo:w-full group-data-[expanded=true]/leo:max-w-3xl">
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
                  />
                )}
              </MessageScrollerItem>
            ))}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton />
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

function AssistantMessage({ message, isLast, canRegenerate, onRegenerate }: AssistantMessageProps) {
  const isStreaming = message.status === "streaming";
  const hasAnswer = message.content.length > 0;
  const showActions = !isStreaming && (hasAnswer || isLast);

  return (
    <div className="flex flex-col gap-3">
      <LeoSteps message={message} />
      {message.status === "error" ? <ReplyError /> : null}
      {hasAnswer || showActions ? (
        <div className="flex flex-col gap-1">
          {hasAnswer ? <AnswerCard text={message.content} isStreaming={isStreaming} /> : null}
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

function ReplyError() {
  const t = useTranslations("leo");
  return (
    <p className="text-destructive text-sm" role="alert">
      {t("message.replyFailed")}
    </p>
  );
}

function AnswerCard({ text, isStreaming }: { readonly text: string; readonly isStreaming: boolean }) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-3 text-sm leading-relaxed">
      <LeoRichText text={text} />
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
    <div className="flex items-center gap-0.5 ps-2">
      {message.content ? <CopyAction text={message.content} /> : null}
      {isLast ? (
        <MessageAction onClick={onRegenerate} disabled={!canRegenerate}>
          <RotateCcw />
          {message.status === "error" ? t("message.tryAgain") : t("message.regenerate")}
        </MessageAction>
      ) : null}
    </div>
  );
}
