"use client";

import { Brain, CircleOff, Undo2 } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

import type { FactsPage } from "../domain/contract";
import { splitFacts } from "../domain/facts";
import { type MemoryWords, useMemoryWords } from "../model/fact-actions";
import { factsResource, loadMoreFacts, useFacts, useFactsQuery } from "../model/facts-resource";
import { useMemorySwitch } from "../model/memory-switch";
import { undoForget, usePendingForget } from "../model/pending-forget";
import { FactCandidates } from "./fact-candidates";
import { FactList } from "./fact-list";
import { ForgetAll } from "./forget-all";
import { ImportedFacts } from "./imported-facts";

function EmptyMemory({ words }: { words: MemoryWords }) {
  const { t } = words;
  return (
    <Empty className="min-h-56">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Brain />
        </EmptyMedia>
        <EmptyTitle>{t("empty.title")}</EmptyTitle>
        <EmptyDescription>{t("empty.description")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

function FactsBody({ page, words }: { page: FactsPage; words: MemoryWords }) {
  const { t } = words;
  const memory = useMemorySwitch();
  const query = useFactsQuery();
  const { candidates, active } = splitFacts(page.items);
  const filtered = query.kind !== null || query.words !== "";
  const { counts } = page;
  const nothing = counts.active === 0 && counts.candidates === 0 && counts.imported === 0 && !filtered;
  return (
    <div className="flex flex-col gap-5">
      {memory.status === "ready" && !memory.data ? (
        <Alert>
          <CircleOff />
          <AlertDescription>{t("off")}</AlertDescription>
        </Alert>
      ) : null}
      <FactCandidates candidates={candidates} words={words} />
      <ImportedFacts count={counts.imported} words={words} />
      {nothing ? <EmptyMemory words={words} /> : null}
      {nothing ? null : (
        <FactList
          active={active}
          total={counts.active}
          words={words}
          onMore={page.next_cursor === null ? null : () => void loadMoreFacts()}
        />
      )}
    </div>
  );
}

/**
 * Что помнит Leo, по фактам (SM-6): у каждого источник, любой можно поправить, закрепить или забыть; кандидаты
 * ждут ответа сверху. Выключенная память ничего не удаляет — окно говорит об этом сверху.
 */
export function MemoryFactsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const words = useMemoryWords();
  const { t } = words;
  const state = useFacts();
  const forgotten = usePendingForget();
  // Внизу — сколько фактов Leo использует во всей памяти; кандидаты ждут ответа и не в счёт.
  const total = state.status === "ready" ? state.data.counts.active : 0;

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="flex h-[min(46rem,90dvh)] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <div className="flex flex-col gap-1 border-b px-6 py-4 pe-12">
          <DialogTitle>{t("dialog.title")}</DialogTitle>
          <DialogDescription>{t("dialog.description")}</DialogDescription>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {state.status === "loading" ? <Skeleton className="h-64 rounded-xl" /> : null}
          {state.status === "error" ? (
            <LoadError title={t("failed.load")} message={state.message} onRetry={() => void factsResource.refresh()} />
          ) : null}
          {state.status === "ready" ? <FactsBody page={state.data} words={words} /> : null}
        </div>
        {total > 0 || forgotten ? (
          <div className="flex items-center justify-between gap-3 border-t px-6 py-3">
            {/* Отмена — здесь, а не в тосте: модальное окно делает тосты недоступными. */}
            <span role="status" className="min-w-0 truncate text-muted-foreground text-sm tabular-nums">
              {forgotten ? t("forgotten") : t("dialog.count", { count: total })}
            </span>
            {forgotten ? (
              <Button variant="outline" size="sm" onClick={() => void undoForget()}>
                <Undo2 data-icon="inline-start" className="rtl:-scale-x-100" />
                {words.common("actions.undo")}
              </Button>
            ) : (
              <ForgetAll count={total} words={words} />
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
