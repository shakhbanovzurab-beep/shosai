"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useFacts } from "@/features/memory/model/facts-resource";
import { MemoryFactsDialog } from "@/features/memory/ui/memory-facts-dialog";

import { SettingsRow } from "../settings-row";

/** «Что помнит Leo»: факты по одному, с источником (SM-6); счётчики — по всей памяти, с сервера. */
export function MemoryFactsRow() {
  const t = useTranslations("memory");
  const words = useTranslations("settings");
  const [open, setOpen] = useState(false);
  const state = useFacts();
  const counts = state.status === "ready" ? state.data.counts : null;

  return (
    <>
      <SettingsRow
        title={t("row.title")}
        description={
          <span className="flex flex-wrap gap-x-1">
            <span>{t("row.facts", { count: counts?.active ?? 0 })}</span>
            {counts && counts.candidates > 0 ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="text-foreground">{t("row.waiting", { count: counts.candidates })}</span>
              </>
            ) : null}
          </span>
        }
      >
        <Button variant="outline" className="rounded-full" onClick={() => setOpen(true)}>
          {words("manage")}
        </Button>
      </SettingsRow>
      <MemoryFactsDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
