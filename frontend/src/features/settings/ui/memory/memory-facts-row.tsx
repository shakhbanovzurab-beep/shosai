"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { splitFacts } from "@/features/memory/domain/facts";
import { useFacts } from "@/features/memory/model/facts-resource";
import { MemoryFactsDialog } from "@/features/memory/ui/memory-facts-dialog";

import { SettingsRow } from "../settings-row";

/** «Что помнит Leo»: факты по одному, с источником (SM-6); сводка выше остаётся лицом раздела. */
export function MemoryFactsRow({ memoryOn }: { memoryOn: boolean }) {
  const t = useTranslations("memory");
  const words = useTranslations("settings");
  const [open, setOpen] = useState(false);
  const state = useFacts();
  const { candidates, active } = splitFacts(state.status === "ready" ? state.data.facts : []);

  return (
    <>
      <SettingsRow
        title={t("row.title")}
        description={
          <span className="flex flex-wrap gap-x-1">
            <span>{t("row.facts", { count: active.length })}</span>
            {candidates.length > 0 ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="text-foreground">{t("row.waiting", { count: candidates.length })}</span>
              </>
            ) : null}
          </span>
        }
      >
        <Button variant="outline" className="rounded-full" onClick={() => setOpen(true)}>
          {words("manage")}
        </Button>
      </SettingsRow>
      <MemoryFactsDialog open={open} onClose={() => setOpen(false)} memoryOn={memoryOn} />
    </>
  );
}
