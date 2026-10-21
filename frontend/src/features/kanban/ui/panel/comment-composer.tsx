"use client";

import { useId, useState } from "react";

import { SendHorizontal } from "lucide-react";
import { useTranslations } from "use-intl";

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupText,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { useIsMac } from "@/features/settings/model/use-is-mac";

import { COMMENT_MAX } from "../../domain/tasks-contract";

// Счётчик знаков появляется у самого предела, а не мешает всё время.
const COUNT_FROM = COMMENT_MAX - 500;

/**
 * Новый комментарий: Ctrl/⌘+Enter или кнопка отправляют, поле сразу пустеет. Если отправить не вышло, текст
 * возвращается в поле — человек ничего не теряет.
 */
export function CommentComposer({ onSend }: { onSend: (body: string) => Promise<boolean> }) {
  const t = useTranslations("kanbanPanel");
  const isMac = useIsMac();
  const [body, setBody] = useState("");
  const hintId = useId();
  const text = body.trim();

  const send = () => {
    if (!text) return;
    setBody("");
    void onSend(text).then((sent) => (sent ? undefined : setBody((current) => current || text)));
  };

  return (
    <InputGroup>
      <InputGroupTextarea
        value={body}
        maxLength={COMMENT_MAX}
        dir="auto"
        rows={2}
        placeholder={t("comments.placeholder")}
        aria-label={t("comments.placeholder")}
        aria-describedby={hintId}
        className="field-sizing-content max-h-60 min-h-16"
        onChange={(event) => setBody(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" || !(event.metaKey || event.ctrlKey)) return;
          event.preventDefault();
          send();
        }}
      />
      <InputGroupAddon align="block-end">
        <InputGroupText id={hintId} className="text-xs">
          {body.length >= COUNT_FROM
            ? t("comments.length", { count: body.length, max: COMMENT_MAX })
            : t("comments.sendHint", { shortcut: isMac ? "⌘ Enter" : "Ctrl+Enter" })}
        </InputGroupText>
        <InputGroupButton variant="default" size="sm" className="ms-auto" disabled={!text} onClick={send}>
          <SendHorizontal data-icon="inline-start" className="rtl:-scale-x-100" />
          {t("comments.send")}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}
