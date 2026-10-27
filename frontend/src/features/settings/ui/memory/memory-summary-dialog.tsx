"use client";

import { useState, useTransition } from "react";

import { Copy, Ellipsis, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import type { MemoryMessageReply, MemorySummary } from "@/features/memory/domain/summary-contract";
import { refreshSummary, summaryResource } from "@/features/memory/model/summary";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { SectionState } from "../section-state";
import { MemorySummaryBody } from "./memory-summary-body";
import { MemorySummaryComposer } from "./memory-summary-composer";
import { MemorySummaryReply } from "./memory-summary-reply";

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
        <DropdownMenuItem onSelect={() => startRefresh(() => refreshSummary(t("summary.refreshFailed")))}>
          <RefreshCw />
          {t("summary.refresh")}
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={summary.sections.length === 0}
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

/**
 * The memory summary: what Leo has learned, written by the model from the facts, with a box to ask about it or
 * correct it; the box's answer and its changes, each undone in place, sit above the box (MM-D3).
 */
export function MemorySummaryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useTranslations("settingsMemory");
  const state = usePollingResource(summaryResource);
  const [draft, setDraft] = useState("");
  const [reply, setReply] = useState<MemoryMessageReply | null>(null);
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
          <SectionState state={state} onRetry={() => void summaryResource.refresh()}>
            {(data) => <MemorySummaryBody summary={data} onSuggest={setDraft} />}
          </SectionState>
        </div>
        {reply ? <MemorySummaryReply key={reply.changes.map((c) => c.fact.id).join()} reply={reply} /> : null}
        <MemorySummaryComposer value={draft} onChange={setDraft} onReply={setReply} />
      </DialogContent>
    </Dialog>
  );
}
