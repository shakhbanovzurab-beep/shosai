"use client";

import { useTransition } from "react";

import { ArrowUp } from "lucide-react";
import { useTranslations } from "use-intl";

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";

import { SUMMARY_MESSAGE_MAX } from "../../domain/memory-contract";
import { sendSummaryMessage } from "../../model/memory-actions";

type ComposerProps = { value: string; onChange: (value: string) => void };

/** "Ask or update": a question about the summary, or something Leo should remember or forget. */
export function MemorySummaryComposer({ value, onChange }: ComposerProps) {
  const t = useTranslations("settingsMemory");
  const [pending, startTransition] = useTransition();
  const canSend = value.trim().length > 0 && !pending;

  const send = () =>
    startTransition(async () => {
      if (await sendSummaryMessage(value.trim(), t)) onChange("");
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
