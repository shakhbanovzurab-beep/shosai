"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { META_VALUE_BUTTON } from "@/components/meta-item";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";

import type { AddressSignal, HubRef } from "../../domain/contract";
import { fileMeeting } from "../../model/meeting-actions";
import { useHubWords } from "../../model/words";
import { HubPicker } from "./hub-picker";

/**
 * The hub the server suggests for a meeting, as one quiet value in the row under its title; its reason and
 * the choice (file it here, or in another hub) open from it.
 */
export function HubSuggestion({ meetingId, hub, signal }: { meetingId: string; hub: HubRef; signal: AddressSignal }) {
  const t = useTranslations("hubMeetings");
  const detail = useTranslations("hubDetail");
  const words = useHubWords();
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const file = (target: HubRef) => {
    setOpen(false);
    void fileMeeting(words, meetingId, target);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="xs" className={META_VALUE_BUTTON}>
          <span className="truncate">{t("chip.suggestion", { hub: hub.name })}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72">
        <PopoverHeader>
          <PopoverTitle>{t("chip.suggestion", { hub: hub.name })}</PopoverTitle>
          <PopoverDescription>{detail(`why.signals.${signal}`)}</PopoverDescription>
        </PopoverHeader>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => file(hub)}>
            {t("chip.file")}
          </Button>
          <HubPicker
            current={null}
            open={picking}
            onOpenChange={setPicking}
            onPick={file}
            trigger={
              <Button size="sm" variant="ghost">
                {t("chip.other")}
              </Button>
            }
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}
