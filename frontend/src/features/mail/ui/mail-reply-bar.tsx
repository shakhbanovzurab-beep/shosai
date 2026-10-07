"use client";

import { type FormEvent, useRef, useState } from "react";

import { Paperclip, Reply, Send, Smile } from "lucide-react";
import { useTranslations } from "next-intl";

import { EmojiButton } from "@/components/emoji/emoji-button";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";

import type { Mail } from "../domain/mail";
import { mailActions } from "../model/mail-store";
import { useMailWords } from "./use-mail-words";

/** Quick reply under an open email; emoji go in at the caret. Remount with `key` per email to reset the draft. */
export function MailReplyBar({ mail }: { mail: Mail }) {
  const t = useTranslations("mail.replyBar");
  const words = useMailWords();
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const recipient = mail.from.name;

  const insertEmoji = (emoji: string) => {
    const input = inputRef.current;
    const start = input?.selectionStart ?? draft.length;
    const end = input?.selectionEnd ?? draft.length;
    setDraft(draft.slice(0, start) + emoji + draft.slice(end));
    requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(start + emoji.length, start + emoji.length);
    });
  };

  const send = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    // Undo puts the text back into the field.
    mailActions.sendReply(mail, words, () => setDraft(text));
  };

  return (
    // me-14 keeps Send clear of the floating Leo launcher in the bottom corner on the end side.
    <form className="me-14" onSubmit={send}>
      <InputGroup>
        <InputGroupAddon align="inline-start">
          <Reply className="rtl:-scale-x-100" />
        </InputGroupAddon>
        <InputGroupInput
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.currentTarget.value)}
          dir="auto"
          className="text-xs"
          placeholder={t("placeholder", { name: recipient })}
          aria-label={t("label", { name: recipient })}
        />
        <InputGroupAddon className="gap-1" align="inline-end">
          <EmojiButton onSelect={insertEmoji}>
            <InputGroupButton variant="ghost" aria-label={t("addEmoji")}>
              <Smile />
            </InputGroupButton>
          </EmojiButton>
          <InputGroupButton variant="ghost" aria-label={t("attachFile")}>
            <Paperclip />
          </InputGroupButton>
          <InputGroupButton type="submit" variant="ghost" aria-label={t("send")} disabled={!draft.trim()}>
            <Send className="rtl:-scale-x-100" />
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}
