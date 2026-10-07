"use client";

import { useRef, useState, useTransition } from "react";

import { ArrowUp, Smile } from "lucide-react";
import { useTranslations } from "next-intl";

import { EmojiButton } from "@/components/emoji/emoji-button";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import { BODY_MAX } from "../domain/contract";
import { useAddFiles } from "../model/attachments";
import { AttachButton, PendingFiles } from "./attachments-field";

type TicketComposerProps = {
  placeholder: string;
  /** Resolves true when sent, so the draft is cleared only on success. */
  onSend: (body: string, files: File[]) => Promise<boolean>;
};

/** Reply box: grows with the text, Enter sends, Shift+Enter adds a line, files via the paperclip or drop. */
export function TicketComposer({ placeholder, onSend }: TicketComposerProps) {
  const t = useTranslations("pagesSupport");
  const addFiles = useAddFiles();
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [sending, startSending] = useTransition();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const canSend = (body.trim().length > 0 || files.length > 0) && !sending;

  const send = () => {
    if (!canSend) return;
    startSending(async () => {
      if (await onSend(body.trim(), files)) {
        setBody("");
        setFiles([]);
      }
    });
  };

  /** Puts the emoji where the caret is (or at the end) and keeps typing from there. */
  const insertEmoji = (emoji: string) => {
    const textarea = textareaRef.current;
    const start = textarea?.selectionStart ?? body.length;
    const end = textarea?.selectionEnd ?? body.length;
    setBody(body.slice(0, start) + emoji + body.slice(end));
    requestAnimationFrame(() => {
      textarea?.focus();
      textarea?.setSelectionRange(start + emoji.length, start + emoji.length);
    });
  };

  return (
    <form
      action={send}
      className="m-3 flex flex-col gap-2 rounded-xl border bg-background p-2 shadow-xs focus-within:ring-2 focus-within:ring-ring/40"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        setFiles((current) => addFiles(current, [...event.dataTransfer.files]));
      }}
    >
      <PendingFiles files={files} onRemove={(index) => setFiles((current) => current.filter((_, i) => i !== index))} />
      <textarea
        ref={textareaRef}
        value={body}
        maxLength={BODY_MAX}
        rows={1}
        onChange={(event) => setBody(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
        aria-label={t("composer.message")}
        dir="auto"
        className="field-sizing-content max-h-48 min-h-10 w-full resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
      />
      {/* pe-14 keeps Send clear of the floating Leo launcher in the bottom end corner. */}
      <div className="flex items-center justify-between pe-14">
        <div className="flex items-center">
          <AttachButton onAdd={(added) => setFiles((current) => addFiles(current, added))} disabled={sending} />
          <EmojiButton onSelect={insertEmoji}>
            <Button type="button" variant="ghost" size="icon-sm" aria-label={t("composer.emoji")} disabled={sending}>
              <Smile />
            </Button>
          </EmojiButton>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden text-muted-foreground text-xs xl:inline">{t("composer.hint")}</span>
          <Button
            type="submit"
            size="icon-sm"
            className="rounded-full"
            disabled={!canSend}
            aria-label={t("composer.send")}
          >
            {sending ? <Spinner /> : <ArrowUp />}
          </Button>
        </div>
      </div>
    </form>
  );
}
