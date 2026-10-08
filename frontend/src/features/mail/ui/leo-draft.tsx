"use client";

import { ChevronDown, PenLine, Send, Trash2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupText,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { Kbd } from "@/components/ui/kbd";

import type { Mail } from "../domain/mail";
import { leoActions, useOpenDraftId } from "../model/leo-store";
import { mailActions } from "../model/mail-store";
import { draftFieldId, reviewDraft } from "./review-draft";
import { useMailWords } from "./use-mail-words";

const WHITESPACE = /\s+/g;

/** Leo's reply under the open email: a one-line preview until the user opens it to review, edit and send it. */
export function LeoDraft({ mail, draft }: { mail: Mail; draft: string }) {
  const isOpen = useOpenDraftId() === mail.id;
  return isOpen ? <DraftEditor mail={mail} draft={draft} /> : <DraftPreview mail={mail} draft={draft} />;
}

function DraftPreview({ mail, draft }: { mail: Mail; draft: string }) {
  const t = useTranslations("mailLeo.draft");

  return (
    // me-14 keeps the row clear of the floating Leo launcher in the bottom corner on the end side.
    <Button
      variant="outline"
      className="me-14 w-auto justify-start"
      aria-label={t("reviewLabel", { name: mail.from.name })}
      onClick={() => reviewDraft(mail.id)}
    >
      <PenLine data-icon="inline-start" />
      <span>{t("drafted")}</span>
      <span dir="auto" className="min-w-0 flex-1 truncate text-start font-normal text-muted-foreground">
        {draft.replace(WHITESPACE, " ")}
      </span>
      <span className="text-muted-foreground">{t("review")}</span>
    </Button>
  );
}

/** Nothing leaves without the user: Send is the approval, and Undo takes it back. */
function DraftEditor({ mail, draft }: { mail: Mail; draft: string }) {
  const t = useTranslations("mailLeo.draft");
  const words = useMailWords();
  const canSend = draft.trim().length > 0;

  const send = () => {
    if (!canSend) return;
    leoActions.closeDraft();
    mailActions.sendReply(mail, words, () => leoActions.openDraft(mail.id));
  };

  return (
    <InputGroup className="me-14 w-auto">
      <InputGroupAddon align="block-start" className="border-b">
        <PenLine />
        <InputGroupText>{t("heading")}</InputGroupText>
        <InputGroupButton size="icon-xs" className="ms-auto" aria-label={t("collapse")} onClick={leoActions.closeDraft}>
          <ChevronDown />
        </InputGroupButton>
      </InputGroupAddon>
      <InputGroupTextarea
        id={draftFieldId(mail.id)}
        value={draft}
        dir="auto"
        aria-label={t("field", { name: mail.from.name })}
        aria-keyshortcuts="Meta+Enter Control+Enter"
        className="max-h-48 min-h-24"
        onChange={(event) => leoActions.editDraft(mail.id, event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            send();
          }
        }}
      />
      <InputGroupAddon align="block-end" className="border-t">
        <InputGroupButton onClick={() => leoActions.discardDraft(mail.id, words)}>
          <Trash2 />
          {t("discard")}
        </InputGroupButton>
        <div className="ms-auto flex items-center gap-2">
          <Kbd className="max-sm:hidden">⌘↵</Kbd>
          <InputGroupButton variant="default" disabled={!canSend} onClick={send}>
            <Send className="rtl:-scale-x-100" />
            {t("send")}
          </InputGroupButton>
        </div>
      </InputGroupAddon>
    </InputGroup>
  );
}
