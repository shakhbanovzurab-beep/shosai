import { useState } from "react";

import { SendHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useTranslations } from "use-intl";

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group";

import { CHAT_TEXT_MAX, type ChatMessage, sendableText } from "../../domain/chat-log";

type CallChatProps = { chat: ChatMessage[]; self: string; notesOn: boolean; onSend: (text: string) => Promise<void> };

/** Чат звонка: сообщения в порядке сервера; с заметками Leo он остаётся во встрече, без них — исчезает с концом. */
export function CallChat({ chat, self, notesOn, onSend }: CallChatProps) {
  const t = useTranslations("meetingRoom");
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
            <div className="flex items-baseline gap-2 text-xs">
              <span dir="auto" className="truncate font-medium">
                {message.identity === self ? t("chat.you") : message.author}
              </span>
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
      <p className="text-muted-foreground text-xs">{t(notesOn ? "chat.keptWithNotes" : "chat.goneAtEnd")}</p>
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
