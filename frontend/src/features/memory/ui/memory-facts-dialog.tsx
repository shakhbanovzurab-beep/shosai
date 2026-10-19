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
import { factsResource, loadMoreFacts, useFacts } from "../model/facts-resource";
import { undoForget, usePendingForget } from "../model/pending-forget";
import { FactCandidates } from "./fact-candidates";
import { FactList } from "./fact-list";
import { ForgetAll } from "./forget-all";

function FactsBody({ page, memoryOn, words }: { page: FactsPage; memoryOn: boolean; words: MemoryWords }) {
  const { t } = words;
  const { candidates, active } = splitFacts(page.facts);
  return (
    <div className="flex flex-col gap-5">
      {memoryOn ? null : (
        <Alert>
          <CircleOff />
          <AlertDescription>{t("off")}</AlertDescription>
        </Alert>
      )}
      <FactCandidates candidates={candidates} words={words} />
      {page.facts.length === 0 ? (
        <Empty className="min-h-56">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Brain />
            </EmptyMedia>
            <EmptyTitle>{t("empty.title")}</EmptyTitle>
            <EmptyDescription>{t("empty.description")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : null}
      {active.length > 0 ? (
        <FactList
          active={active}
          words={words}
          onMore={page.next_cursor === null ? null : () => void loadMoreFacts()}
        />
      ) : null}
    </div>
  );
}

/**
 * Что помнит Leo, по фактам (SM-6): у каждого источник, любой можно поправить, закрепить или забыть; кандидаты
 * ждут ответа сверху. `memoryOn` — переключатель памяти: выключенная память ничего не удаляет.
 */
export function MemoryFactsDialog({
  open,
  onClose,
  memoryOn,
}: {
  open: boolean;
  onClose: () => void;
  memoryOn: boolean;
}) {
  const words = useMemoryWords();
  const { t } = words;
  const state = useFacts();
  const forgotten = usePendingForget();
  // Внизу — факты, которые Leo использует; кандидаты ждут ответа и не в счёт.
  const { active } = splitFacts(state.status === "ready" ? state.data.facts : []);

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
          {state.status === "ready" ? <FactsBody page={state.data} memoryOn={memoryOn} words={words} /> : null}
        </div>
        {active.length > 0 || forgotten ? (
          <div className="flex items-center justify-between gap-3 border-t px-6 py-3">
            {/* Отмена — здесь, а не в тосте: модальное окно делает тосты недоступными. */}
            <span role="status" className="min-w-0 truncate text-muted-foreground text-sm tabular-nums">
              {forgotten ? t("forgotten") : t("dialog.count", { count: active.length })}
            </span>
            {forgotten ? (
              <Button variant="outline" size="sm" onClick={undoForget}>
                <Undo2 data-icon="inline-start" className="rtl:-scale-x-100" />
                {words.common("actions.undo")}
              </Button>
            ) : (
              <ForgetAll count={active.length} words={words} />
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
