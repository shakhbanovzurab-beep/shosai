"use client";

import * as React from "react";

import { FileText, Pencil } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Attachment, AttachmentContent, AttachmentMedia } from "@/components/ui/attachment";
import { AttachmentDescription, AttachmentGroup, AttachmentTitle } from "@/components/ui/attachment-parts";
import { Bubble, BubbleContent, BubbleGroup } from "@/components/ui/bubble";
import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupTextarea } from "@/components/ui/input-group";
import { Message, MessageContent } from "@/components/ui/message";
import { formatBytes } from "@/i18n/format-units";

import type { LeoMessage } from "../domain/types";
import { CopyAction, MessageAction } from "./leo-message-actions";

interface LeoUserMessageProps {
  readonly message: LeoMessage;
  readonly canEdit: boolean;
  readonly onEdit: (content: string) => void;
}

export function LeoUserMessage({ message, canEdit, onEdit }: LeoUserMessageProps) {
  const t = useTranslations("leo");
  const [isEditing, setIsEditing] = React.useState(false);

  return (
    <Message align="end">
      <MessageContent className="group/user-message">
        {message.attachments?.length ? <UserAttachments message={message} /> : null}
        {isEditing ? (
          <UserMessageEditor
            initialValue={message.content}
            onCancel={() => setIsEditing(false)}
            onSubmit={(content) => {
              setIsEditing(false);
              onEdit(content);
            }}
          />
        ) : (
          <>
            {message.content ? (
              // Full width so the bubble's max width is measured against the chat, not against its own text.
              <BubbleGroup className="w-full items-end">
                <Bubble align="end" variant="secondary">
                  <BubbleContent dir="auto" className="whitespace-pre-wrap rounded-2xl">
                    {message.content}
                  </BubbleContent>
                </Bubble>
              </BubbleGroup>
            ) : null}
            <div className="flex items-center justify-end gap-0.5 opacity-0 pointer-coarse:opacity-100 transition-opacity focus-within:opacity-100 group-hover/user-message:opacity-100">
              {message.content ? <CopyAction text={message.content} /> : null}
              {canEdit ? (
                <MessageAction onClick={() => setIsEditing(true)}>
                  <Pencil />
                  {t("message.edit")}
                </MessageAction>
              ) : null}
            </div>
          </>
        )}
      </MessageContent>
    </Message>
  );
}

function UserAttachments({ message }: { readonly message: LeoMessage }) {
  const t = useTranslations("leo");
  const locale = useLocale();
  return (
    <AttachmentGroup className="justify-end" aria-label={t("message.attachedFiles")}>
      {message.attachments?.map((attachment) => (
        <Attachment key={attachment.id} size="xs" className="min-w-0 max-w-56">
          <AttachmentMedia>
            <FileText />
          </AttachmentMedia>
          <AttachmentContent>
            <AttachmentTitle>{attachment.name}</AttachmentTitle>
            <AttachmentDescription>{formatBytes(locale, attachment.size)}</AttachmentDescription>
          </AttachmentContent>
        </Attachment>
      ))}
    </AttachmentGroup>
  );
}

interface UserMessageEditorProps {
  readonly initialValue: string;
  readonly onCancel: () => void;
  readonly onSubmit: (content: string) => void;
}

function UserMessageEditor({ initialValue, onCancel, onSubmit }: UserMessageEditorProps) {
  const t = useTranslations("leo");
  const tCommon = useTranslations("common");
  const [value, setValue] = React.useState(initialValue);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  // The editor only opens from an explicit Edit click, so move focus into it with the caret at the end.
  React.useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }, []);
  const canSubmit = value.trim().length > 0 && value.trim() !== initialValue.trim();

  const submit = () => {
    if (canSubmit) onSubmit(value.trim());
  };

  return (
    <form
      className="w-full"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <InputGroup className="rounded-2xl bg-secondary">
        <InputGroupTextarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              // Only leave edit mode; don't let Escape close the whole chat.
              event.stopPropagation();
              onCancel();
            } else if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          aria-label={t("message.editMessage")}
          maxLength={4000}
          className="max-h-40 min-h-11 px-3.5 pt-3 text-sm"
        />
        <InputGroupAddon align="block-end" className="justify-end gap-1.5 pb-2.5">
          <Button type="button" variant="ghost" size="sm" className="rounded-full" onClick={onCancel}>
            {tCommon("actions.cancel")}
          </Button>
          <Button type="submit" size="sm" className="rounded-full" disabled={!canSubmit}>
            {t("composer.send")}
          </Button>
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}
