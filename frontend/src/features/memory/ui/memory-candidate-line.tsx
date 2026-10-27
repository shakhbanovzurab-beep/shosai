"use client";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { useAnswerCandidate, useThreadCandidates } from "../model/thread-candidates";

/**
 * Строка под ответом Leo (MM-D1): что Leo может запомнить из этой беседы, с «Запомнить» и «Не запоминать».
 * Тихая: без уведомлений; пока человек не ответил, Leo кандидата не использует.
 */
export function MemoryCandidateLine({ threadId, answerId }: { threadId: string; answerId: string }) {
  const t = useTranslations("memory");
  const candidates = useThreadCandidates(threadId, answerId);
  const answer = useAnswerCandidate(threadId, answerId);
  if (candidates.length === 0) return null;
  return (
    <ul aria-label={t("line.label")} className="flex flex-col gap-1 ps-2">
      {candidates.map((fact) => (
        <li key={fact.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-muted-foreground text-xs">
          <span>{t("line.label")}</span>
          <span dir="auto" className="text-foreground">
            {fact.statement}
          </span>
          <span className="flex items-center gap-1">
            <Button variant="link" size="xs" className="px-0" onClick={() => void answer(fact, true, t("failed.save"))}>
              {t("candidates.accept")}
            </Button>
            <span aria-hidden="true">·</span>
            <Button
              variant="link"
              size="xs"
              className="px-0"
              onClick={() => void answer(fact, false, t("failed.save"))}
            >
              {t("candidates.reject")}
            </Button>
          </span>
        </li>
      ))}
    </ul>
  );
}
