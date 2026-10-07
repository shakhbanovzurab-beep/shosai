"use client";

import { useState } from "react";

import Link from "next/link";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import { useSettingsDialog } from "../../model/dialog-store";
import { SettingsRow } from "../settings-row";
import { MemorySummaryDialog } from "./memory-summary-dialog";

const linkClass = "underline underline-offset-2 hover:text-foreground";

/** "Memory summary": the overview of what Leo knows, opened in its own dialog. */
export function MemorySummaryRow() {
  const t = useTranslations("settingsMemory");
  const words = useTranslations("settings");
  const [open, setOpen] = useState(false);
  const closeSettings = useSettingsDialog((s) => s.close);

  return (
    <>
      <SettingsRow
        title={t("summary.title")}
        description={t.rich("summary.description", {
          link: (chunks) => (
            <Link href="/app/studio" onClick={closeSettings} className={linkClass}>
              {chunks}
            </Link>
          ),
        })}
      >
        <Button variant="outline" className="rounded-full" onClick={() => setOpen(true)}>
          {words("manage")}
        </Button>
      </SettingsRow>
      <MemorySummaryDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
