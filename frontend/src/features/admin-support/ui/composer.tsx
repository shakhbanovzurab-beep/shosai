"use client";

import { useRef, useState } from "react";

import { cn } from "cn";
import { ArrowUp, FileText, Paperclip, X } from "lucide-react";

import { Attachment, AttachmentContent, AttachmentMedia } from "@/components/ui/attachment";
import {
  AttachmentAction,
  AttachmentActions,
  AttachmentDescription,
  AttachmentGroup,
  AttachmentTitle,
} from "@/components/ui/attachment-parts";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group";
import { Kbd } from "@/components/ui/kbd";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { type AttachmentMeta, MAX_ATTACHMENTS, MESSAGE_MAX, type MessageKind } from "../domain/contract";
import { formatBytes } from "../domain/format";
import { addFiles } from "../model/composer-files";
import { sendMessage } from "../model/support-actions";
import { useDraft, useInbox } from "../model/support-store";
import { CannedReplies } from "./canned-replies";

/** Reply or internal note: Enter sends, Shift+Enter adds a line; the draft survives switching conversations. */
export function Composer({ conversationId, userName }: { conversationId: string; userName: string }) {
  const draft = useDraft(conversationId);
  const setDraft = useInbox((s) => s.setDraft);
  const [files, setFiles] = useState<AttachmentMeta[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const note = draft.kind === "note";
  const canSend = draft.body.trim().length > 0 || files.length > 0;
  const firstName = userName.split(" ")[0] ?? userName;

  const submit = () => {
    if (!canSend) return;
    sendMessage(conversationId, { body: draft.body.trim(), kind: draft.kind, attachments: files });
    setDraft(conversationId, { body: "" });
    setFiles([]);
  };

  const insert = (text: string) => {
    const body = draft.body.trim() ? `${draft.body.trimEnd()}\n${text}` : text;
    setDraft(conversationId, { body });
    textareaRef.current?.focus();
  };

  return (
    <form
      className="flex flex-col gap-2 border-t bg-background px-3 pt-2 pb-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        setFiles((current) => addFiles(current, [...event.dataTransfer.files]));
      }}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-2">
        <ToggleGroup
          type="single"
          size="sm"
          spacing={1}
          value={draft.kind}
          onValueChange={(value) => {
            if (value) setDraft(conversationId, { kind: value as MessageKind });
          }}
          aria-label="Тип сообщения"
        >
          <ToggleGroupItem value="reply" className="data-[state=on]:bg-muted data-[state=on]:text-foreground">
            Ответ
          </ToggleGroupItem>
          <ToggleGroupItem
            value="note"
            className="data-[state=on]:bg-amber-100 data-[state=on]:text-amber-900 dark:data-[state=on]:bg-amber-950/60 dark:data-[state=on]:text-amber-200"
          >
            Внутренняя заметка
          </ToggleGroupItem>
        </ToggleGroup>
        {files.length > 0 ? (
          <AttachmentGroup aria-label="Файлы к отправке" className="w-full">
            {files.map((file) => (
              <Attachment key={file.name} size="xs" className="min-w-0 max-w-48">
                <AttachmentMedia>
                  <FileText />
                </AttachmentMedia>
                <AttachmentContent>
                  <AttachmentTitle>{file.name}</AttachmentTitle>
                  <AttachmentDescription>{formatBytes(file.size_bytes)}</AttachmentDescription>
                </AttachmentContent>
                <AttachmentActions>
                  <AttachmentAction
                    aria-label={`Убрать ${file.name}`}
                    onClick={() => setFiles((current) => current.filter((f) => f.name !== file.name))}
                  >
                    <X />
                  </AttachmentAction>
                </AttachmentActions>
              </Attachment>
            ))}
          </AttachmentGroup>
        ) : null}
        <InputGroup
          className={cn(
            "rounded-xl",
            note && "border-amber-400/70 border-dashed bg-amber-50/60 dark:border-amber-500/40 dark:bg-amber-950/30",
          )}
        >
          <InputGroupTextarea
            ref={textareaRef}
            value={draft.body}
            maxLength={MESSAGE_MAX}
            rows={2}
            onChange={(event) => setDraft(conversationId, { body: event.target.value })}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={note ? "Заметка видна только команде…" : `Ответ для ${firstName}…`}
            aria-label={note ? "Текст внутренней заметки" : "Текст ответа"}
            className="max-h-48 min-h-16 px-3 text-sm"
          />
          <InputGroupAddon align="block-end" className="gap-1">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="sr-only"
              tabIndex={-1}
              aria-hidden="true"
              onChange={(event) => {
                const picked = event.target.files ? [...event.target.files] : [];
                setFiles((current) => addFiles(current, picked));
                event.target.value = "";
              }}
            />
            <InputGroupButton
              size="icon-sm"
              aria-label="Прикрепить файлы"
              title={`До ${MAX_ATTACHMENTS} файлов, до 20 МБ каждый`}
              disabled={files.length >= MAX_ATTACHMENTS}
              onClick={() => fileInputRef.current?.click()}
            >
              <Paperclip />
            </InputGroupButton>
            <CannedReplies firstName={firstName} onInsert={insert} />
            <span className="ml-auto hidden items-center gap-1 text-muted-foreground text-xs md:inline-flex">
              <Kbd>Enter</Kbd> отправить · <Kbd>Shift+Enter</Kbd> новая строка
            </span>
            <InputGroupButton type="submit" variant="default" size="sm" className="max-md:ml-auto" disabled={!canSend}>
              {note ? "Сохранить" : "Отправить"}
              <ArrowUp />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </div>
    </form>
  );
}
