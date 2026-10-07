"use client";

import { useId, useState } from "react";

import { UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { ThreadSummary } from "../../domain/contract";
import { assignOwner } from "../../model/thread-actions";
import { useHubWords } from "../../model/words";

/** "Assign": offered only while nobody owns it, which is a valid state, not an error. */
export function AssignPopover({ thread, className }: { thread: ThreadSummary; className?: string }) {
  const t = useTranslations("hubBlocks");
  const common = useTranslations("common");
  const words = useHubWords();
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="xs" className={className}>
          <UserPlus data-icon="inline-start" aria-hidden="true" />
          {t("unresolved.assign")}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-3">
        <form
          className="flex flex-col gap-2.5"
          action={(data) => {
            const owner = String(data.get("owner") ?? "").trim();
            if (!owner) return;
            setOpen(false);
            void assignOwner(words, thread, owner);
          }}
        >
          <Label htmlFor={id} className="font-medium text-sm">
            {t("unresolved.assignTitle")}
          </Label>
          <Input
            id={id}
            name="owner"
            required
            maxLength={80}
            autoComplete="off"
            dir="auto"
            placeholder={t("unresolved.assignPlaceholder")}
            aria-label={t("unresolved.assignLabel")}
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" className="bg-transparent" onClick={() => setOpen(false)}>
              {common("actions.cancel")}
            </Button>
            <Button type="submit" size="sm">
              {t("unresolved.assign")}
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
