"use client";

import { useState, useTransition } from "react";

import { Copy, CornerDownRight, Ellipsis, RefreshCw } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "next-intl";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { MemorySummary } from "../../domain/memory-contract";
import { refreshMemorySummary } from "../../model/memory-actions";
import { memorySummaryResource } from "../../model/settings-resources";
import { SectionState } from "../section-state";
import { MemorySummaryComposer } from "./memory-summary-composer";

const asText = (summary: MemorySummary) => summary.sections.map((s) => `${s.title}\n${s.body}`).join("\n\n");

/** "Updated 19 hours ago", kept current once a minute while the dialog is open (it only renders in the browser). */
function UpdatedAgo({ at }: { at: string }) {
  const t = useTranslations("settingsMemory");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  // An update newer than the last tick reads "now", never "in 20 seconds".
  const updated = new Date(Math.min(Date.parse(at), now.getTime()));
  return (
    <span className="text-muted-foreground text-sm">
      {t("summary.updated", { ago: format.relativeTime(updated, now) })}
    </span>
  );
}

function SummaryMenu({ summary }: { summary: MemorySummary }) {
  const t = useTranslations("settingsMemory");
  const [refreshing, startRefresh] = useTransition();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={t("summary.actions")} disabled={refreshing}>
          <Ellipsis />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuItem onSelect={() => startRefresh(() => refreshMemorySummary(t))}>
          <RefreshCw />
          {t("summary.refresh")}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() =>
            navigator.clipboard.writeText(asText(summary)).then(
              () => toast.success(t("summary.copied")),
              () => toast.error(t("summary.copyFailed")),
            )
          }
        >
          <Copy />
          {t("summary.copy")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** What Leo wrote: its sections and suggested questions, each in the direction of its own text. */
function SummaryBody({ summary, onSuggest }: { summary: MemorySummary; onSuggest: (text: string) => void }) {
  const t = useTranslations("settingsMemory");
  return (
    <div className="flex flex-col gap-6">
      {summary.sections.map((section) => (
        <section key={section.title} className="flex flex-col gap-2">
          <h3 dir="auto" className="font-semibold text-lg">
            {section.title}
          </h3>
          <p dir="auto" className="whitespace-pre-line text-[15px] leading-7">
            {section.body}
          </p>
        </section>
      ))}
      {summary.suggestions.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h3 className="font-semibold text-lg">{t("summary.learnMore")}</h3>
          <ul className="flex flex-col gap-2">
            {summary.suggestions.map((suggestion) => (
              <li key={suggestion} className="flex gap-2">
                <CornerDownRight
                  className="mt-1 size-4 shrink-0 text-muted-foreground rtl:-scale-x-100"
                  aria-hidden="true"
                />
                <button
                  type="button"
                  dir="auto"
                  onClick={() => onSuggest(suggestion)}
                  className="cursor-pointer text-start underline decoration-dotted underline-offset-4 hover:decoration-solid focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

/** ChatGPT-style memory summary: what Leo has learned, with a box to ask about it or correct it. */
export function MemorySummaryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useTranslations("settingsMemory");
  const state = usePollingResource(memorySummaryResource);
  const [draft, setDraft] = useState("");
  const summary = state.status === "ready" ? state.data : null;

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="flex h-[min(46rem,90dvh)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <div className="flex items-center gap-3 border-b px-6 py-4 pe-12">
          <DialogTitle>{t("summary.title")}</DialogTitle>
          {summary?.updated_at ? <UpdatedAgo at={summary.updated_at} /> : null}
          {summary ? <SummaryMenu summary={summary} /> : null}
          <DialogDescription className="sr-only">{t("summary.dialogDescription")}</DialogDescription>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <SectionState state={state} onRetry={() => void memorySummaryResource.refresh()}>
            {(data) => <SummaryBody summary={data} onSuggest={setDraft} />}
          </SectionState>
        </div>
        <MemorySummaryComposer value={draft} onChange={setDraft} />
      </DialogContent>
    </Dialog>
  );
}
