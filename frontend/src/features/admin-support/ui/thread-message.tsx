"use client";

import type { ReactNode } from "react";

import { Check, CheckCheck, CircleAlert, FileText, ImageIcon, Lock } from "lucide-react";

import { Attachment, AttachmentContent, AttachmentMedia } from "@/components/ui/attachment";
import {
  AttachmentDescription,
  AttachmentGroup,
  AttachmentTitle,
  AttachmentTrigger,
} from "@/components/ui/attachment-parts";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Bubble, BubbleContent, BubbleGroup } from "@/components/ui/bubble";
import { Button } from "@/components/ui/button";
import { Message, MessageAvatar, MessageContent, MessageFooter, MessageHeader } from "@/components/ui/message";
import { Spinner } from "@/components/ui/spinner";
import { getInitials } from "@/lib/utils";

import type { AttachmentMeta, SupportAttachment, SupportMessage } from "../domain/contract";
import { formatBytes, formatDateTime, formatTime } from "../domain/format";
import type { OutboxItem } from "../model/support-store";

/** Internal notes use the amber palette so they never pass for a reply the user can see. */
const NOTE_BUBBLE =
  "*:data-[slot=bubble-content]:border-dashed *:data-[slot=bubble-content]:border-amber-400/70 *:data-[slot=bubble-content]:bg-amber-50 *:data-[slot=bubble-content]:text-foreground dark:*:data-[slot=bubble-content]:border-amber-500/40 dark:*:data-[slot=bubble-content]:bg-amber-950/40";

function Files({ files }: { files: (SupportAttachment | AttachmentMeta)[] }) {
  if (files.length === 0) return null;
  return (
    <AttachmentGroup aria-label="Вложения" className="max-w-full">
      {files.map((file) => {
        const url = "url" in file ? file.url : null;
        const Icon = file.content_type.startsWith("image/") ? ImageIcon : FileText;
        return (
          <Attachment key={file.name} size="xs" className="min-w-0 max-w-56">
            <AttachmentMedia>
              <Icon />
            </AttachmentMedia>
            <AttachmentContent>
              <AttachmentTitle>{file.name}</AttachmentTitle>
              <AttachmentDescription>
                {url ? formatBytes(file.size_bytes) : `${formatBytes(file.size_bytes)} · только метаданные`}
              </AttachmentDescription>
            </AttachmentContent>
            {url ? (
              <AttachmentTrigger asChild>
                <a href={url} target="_blank" rel="noreferrer">
                  <span className="sr-only">Открыть {file.name}</span>
                </a>
              </AttachmentTrigger>
            ) : null}
          </Attachment>
        );
      })}
    </AttachmentGroup>
  );
}

export function ReadStatus({ readAt }: { readAt: string | null }) {
  return readAt ? (
    <span className="inline-flex items-center gap-1" title={`Прочитано ${formatDateTime(readAt)}`}>
      <CheckCheck className="size-3.5 text-primary" aria-hidden="true" />
      Прочитано
    </span>
  ) : (
    <span className="inline-flex items-center gap-1">
      <Check className="size-3.5" aria-hidden="true" />
      Доставлено
    </span>
  );
}

export type BubbleMessage = {
  author: "user" | "agent";
  kind: SupportMessage["kind"];
  name: string;
  body: string;
  files: (SupportAttachment | AttachmentMeta)[];
  createdAt: string;
  footer?: ReactNode;
};

export function ThreadMessage({ message }: { message: BubbleMessage }) {
  const fromUser = message.author === "user";
  const note = message.kind === "note";
  let variant: "muted" | "outline" | "default" = "default";
  if (fromUser) variant = "muted";
  else if (note) variant = "outline";
  return (
    <Message align={fromUser ? "start" : "end"}>
      <MessageAvatar>
        <Avatar>
          <AvatarFallback className="bg-muted text-foreground text-xs">{getInitials(message.name)}</AvatarFallback>
        </Avatar>
      </MessageAvatar>
      <MessageContent>
        <MessageHeader className="gap-1.5">
          {note ? (
            <>
              <Lock className="size-3 text-amber-600 dark:text-amber-400" aria-hidden="true" />
              <span className="text-amber-700 dark:text-amber-300">Внутренняя заметка</span>
              <span aria-hidden="true">·</span>
            </>
          ) : null}
          {message.name}
        </MessageHeader>
        {message.body ? (
          <BubbleGroup>
            <Bubble variant={variant} align={fromUser ? "start" : "end"} className={note ? NOTE_BUBBLE : undefined}>
              <BubbleContent className="whitespace-pre-line">{message.body}</BubbleContent>
            </Bubble>
          </BubbleGroup>
        ) : null}
        <Files files={message.files} />
        <MessageFooter className="gap-2">
          <time dateTime={message.createdAt} title={formatDateTime(message.createdAt)}>
            {formatTime(message.createdAt)}
          </time>
          {message.footer}
        </MessageFooter>
      </MessageContent>
    </Message>
  );
}

export function OutboxFooter({
  item,
  onRetry,
  onDiscard,
}: {
  item: OutboxItem;
  onRetry: () => void;
  onDiscard: () => void;
}) {
  if (item.status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 text-destructive" role="status">
        <CircleAlert className="size-3.5" aria-hidden="true" />
        Не отправлено
        <Button variant="link" size="xs" className="h-auto px-1" onClick={onRetry}>
          Повторить
        </Button>
        <Button variant="link" size="xs" className="h-auto px-1 text-muted-foreground" onClick={onDiscard}>
          Удалить
        </Button>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1" role="status">
      <Spinner className="size-3" />
      Отправка…
    </span>
  );
}
