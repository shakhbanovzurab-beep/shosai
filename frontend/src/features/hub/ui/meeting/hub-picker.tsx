"use client";

import type { ReactNode } from "react";

import { Check } from "lucide-react";
import { useTranslations } from "use-intl";

import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";

import type { HubRef } from "../../domain/contract";
import { useHubList } from "../../model/hooks";

function Choices({ current, onPick }: { current: string | null; onPick: (hub: HubRef) => void }) {
  const t = useTranslations("hubMeetings");
  const hubWords = useTranslations("hub");
  const list = useHubList(false);
  if (list.status === "loading")
    return (
      <div className="flex flex-col gap-2 p-2" aria-busy="true">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-5 w-1/2" />
      </div>
    );
  if (list.status === "error") return <p className="p-3 text-muted-foreground text-sm">{hubWords("list.loadError")}</p>;
  return (
    <Command>
      <CommandInput placeholder={t("chip.pickerSearch")} dir="auto" />
      <CommandList>
        <CommandEmpty>{t("chip.pickerEmpty")}</CommandEmpty>
        <CommandGroup>
          {list.data.hubs.map((hub) => (
            <CommandItem key={hub.id} value={hub.name} onSelect={() => onPick({ id: hub.id, name: hub.name })}>
              <span dir="auto" className="min-w-0 flex-1 truncate">
                {hub.name}
              </span>
              {hub.id === current ? <Check aria-hidden="true" /> : null}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}

/** Choosing a hub for a meeting by hand: the active hubs, searchable, loaded when the list opens. */
export function HubPicker({
  trigger,
  current,
  open,
  onOpenChange,
  onPick,
}: {
  trigger: ReactNode;
  current: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (hub: HubRef) => void;
}) {
  const t = useTranslations("hubMeetings");
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0" aria-label={t("chip.pickerTitle")}>
        {open ? (
          <Choices
            current={current}
            onPick={(hub) => {
              onOpenChange(false);
              onPick(hub);
            }}
          />
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
