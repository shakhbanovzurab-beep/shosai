import { useState } from "react";

import { SendHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group";

import type { BroadcastMessage } from "../../domain/broadcast";
import { CHAT_TEXT_MAX, sendableText } from "../../domain/chat-log";

type BroadcastChatProps = { chat: BroadcastMessage[]; onSend: (text: string) => Promise<void> };

/** Чат трансляции: зал спрашивает, сцена отвечает — её сообщения отмечены. */
export function BroadcastChat({ chat, onSend }: BroadcastChatProps) {
  const t = useTranslations("meetingBroadcast");
  const format = useFormatter();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  async function send() {
    const text = sendableText(draft);
    if (text === null || sending) return;
    setSending(true);
    const sent = await onSend(text).then(
      () => true,
      () => false,
    );
    setSending(false);
    if (sent) setDraft("");
    else toast.error(t("chat.sendFailed"));
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <ol
        aria-label={t("chat.label")}
        aria-live="polite"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain"
      >
        {chat.length === 0 ? (
          <li className="py-8 text-center text-muted-foreground text-sm">{t("chat.empty")}</li>
        ) : null}
        {chat.map((message) => (
          <li key={message.id} className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2 text-xs">
              <span dir="auto" className="truncate font-medium">
                {message.mine ? t("chat.you") : message.author}
              </span>
              {message.fromStage ? <Badge variant="secondary">{t("chat.stageBadge")}</Badge> : null}
              <time dateTime={message.sentAt} className="shrink-0 text-muted-foreground tabular-nums">
                {format.dateTime(new Date(message.sentAt), { hour: "numeric", minute: "2-digit" })}
              </time>
            </div>
            <p dir="auto" className="whitespace-pre-wrap break-words text-sm">
              {message.text}
            </p>
          </li>
        ))}
      </ol>
      <InputGroup>
        <InputGroupTextarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
            event.preventDefault();
            void send();
          }}
          maxLength={CHAT_TEXT_MAX}
          rows={2}
          dir="auto"
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.placeholder")}
        />
        <InputGroupAddon align="block-end">
          <InputGroupButton
            className="ms-auto"
            size="icon-sm"
            disabled={sendableText(draft) === null || sending}
            onClick={() => void send()}
            aria-label={t("chat.send")}
          >
            <SendHorizontal aria-hidden="true" className="rtl:-scale-x-100" />
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </div>
  );
}
