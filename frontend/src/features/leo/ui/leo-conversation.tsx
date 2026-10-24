"use client";

import type { LeoChat } from "../model/leo-chat";
import { LeoConversationLoading } from "./leo-conversation-loading";
import { LeoEmptyState } from "./leo-empty-state";
import { LeoMessageList } from "./leo-message-list";
import type { LeoPlace } from "./leo-place";

/** Разговор панели: заготовка, пока тред читается, приветствие без вопросов или сами сообщения. */
export function LeoConversation({
  chat,
  place,
  pathname,
}: {
  readonly chat: LeoChat;
  readonly place: LeoPlace;
  readonly pathname: string;
}) {
  if (chat.loading) return <LeoConversationLoading />;
  if (chat.messages.length === 0) {
    return <LeoEmptyState pathname={pathname} scope={place.scope} notice={place.notice} onSelect={chat.send} />;
  }
  return (
    <LeoMessageList
      messages={chat.messages}
      isBusy={chat.isBusy}
      earlier={chat.earlier}
      onRegenerate={chat.regenerate}
      onEditLast={chat.editLast}
      onProposal={chat.addProposal}
    />
  );
}
