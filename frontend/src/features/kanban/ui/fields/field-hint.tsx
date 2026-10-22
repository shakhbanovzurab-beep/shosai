"use client";

import { CircleHelp } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { TimeStickerId } from "../../domain/stickers-contract";

/** «?» у поля времени: что оно считает, словами человека. Открывается нажатием — и мышью, и пальцем. */
export function FieldHint({ field, name }: { field: TimeStickerId; name: string }) {
  const t = useTranslations("kanbanFields");
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          className="shrink-0 text-muted-foreground"
          aria-label={t("hintFor", { name })}
        >
          <CircleHelp aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(20rem,calc(100vw-2rem))] p-3 text-muted-foreground">
        <p className="[text-align:match-parent]">{t(`hints.${field}`)}</p>
      </PopoverContent>
    </Popover>
  );
}
