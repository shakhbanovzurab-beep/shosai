"use client";

import { useTransition } from "react";

import { ArrowUp } from "lucide-react";
import { useTranslations } from "use-intl";

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { type MemoryMessageReply, SUMMARY_MESSAGE_MAX } from "@/features/memory/domain/summary-contract";
import { sendSummaryMessage } from "@/features/memory/model/summary";

type ComposerProps = {
  value: string;
  onChange: (value: string) => void;
  /** Leo's answer and changes, shown above the box. */
  onReply: (reply: MemoryMessageReply) => void;
};

/** "Ask or update": a question about the summary, or something Leo should remember, correct or forget. */
export function MemorySummaryComposer({ value, onChange, onReply }: ComposerProps) {
  const t = useTranslations("settingsMemory");
  const [pending, startTransition] = useTransition();
  const canSend = value.trim().length > 0 && !pending;

  const send = () =>
    startTransition(async () => {
      // Один ключ на сообщение: повтор того же запроса сервер отвечает первым результатом.
      const reply = await sendSummaryMessage(value.trim(), crypto.randomUUID(), t("composer.sendFailed"));
      if (reply === null) return;
      onReply(reply);
      onChange("");
    });

  return (
    <form action={send} className="border-t bg-background p-4">
      <InputGroup className="h-12 rounded-full pe-1.5">
        <InputGroupInput
          value={value}
          dir="auto"
          maxLength={SUMMARY_MESSAGE_MAX}
          onChange={(event) => onChange(event.currentTarget.value)}
          placeholder={t("composer.placeholder")}
          aria-label={t("composer.label")}
          className="ps-5"
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            type="submit"
            variant="default"
            size="icon-sm"
            className="size-9 rounded-full"
            disabled={!canSend}
            aria-label={t("composer.send")}
          >
            {pending ? <Spinner /> : <ArrowUp />}
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}
