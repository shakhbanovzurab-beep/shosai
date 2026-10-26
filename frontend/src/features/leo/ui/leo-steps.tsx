"use client";

import * as React from "react";

import { ChevronDown } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { formatDuration } from "@/i18n/format-units";

import { getStepsSummary, type StepsSummary } from "../domain/step-summary";
import type { LeoMessage } from "../domain/types";
import { useElapsed } from "../model/use-elapsed";
import { LeoStepsTimeline } from "./leo-steps-timeline";

/**
 * Состояние «думает» над ответом Leo: пока он работает — «Думаю» с живым таймером, после — «Работал N с»;
 * под заголовком лента шагов, источников и итога. Лента открыта, пока ответа нет, и складывается, когда он
 * начался; человек раскрывает её снова.
 */
export function LeoSteps({ message }: { readonly message: LeoMessage }) {
  const steps = message.steps ?? [];
  const hasAnswer = message.content.length > 0;

  const [open, setOpen] = React.useState(!hasAnswer);
  const [prevHasAnswer, setPrevHasAnswer] = React.useState(hasAnswer);
  if (hasAnswer !== prevHasAnswer) {
    setPrevHasAnswer(hasAnswer);
    if (hasAnswer) setOpen(false);
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="group/steps flex items-center gap-1.5 rounded-md text-muted-foreground text-sm outline-none transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
        <ChevronDown
          aria-hidden="true"
          className="size-4 shrink-0 transition-transform group-data-[state=closed]/steps:-rotate-90 motion-reduce:transition-none rtl:group-data-[state=closed]/steps:rotate-90"
        />
        <Heading summary={getStepsSummary(message, steps)} startedAt={message.startedAt} />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <LeoStepsTimeline message={message} steps={steps} />
      </CollapsibleContent>
    </Collapsible>
  );
}

function Heading({ summary, startedAt }: { readonly summary: StepsSummary; readonly startedAt?: number }) {
  const t = useTranslations("leo");
  const locale = useLocale();
  switch (summary.kind) {
    case "running":
    case "starting":
      return <Thinking startedAt={startedAt} />;
    case "stopped":
      return <span>{t("steps.stoppedAfter", { duration: formatDuration(locale, summary.ms) })}</span>;
    case "error":
      return <span>{t("steps.somethingWrong")}</span>;
    default:
      return (
        <span className="text-foreground">
          {t("steps.workedFor", { duration: formatDuration(locale, summary.ms) })}
        </span>
      );
  }
}

/** «Думаю» и таймер хода; без времени начала (ответ из старой вкладки) — счёт от появления заголовка. */
function Thinking({ startedAt }: { readonly startedAt?: number }) {
  const t = useTranslations("leo");
  const locale = useLocale();
  const [shownAt] = React.useState(Date.now);
  const elapsed = useElapsed(startedAt ?? shownAt);
  return (
    <>
      <span className="shimmer" aria-live="polite">
        {t("steps.thinking")}
      </span>
      <span className="text-muted-foreground/70 tabular-nums">{formatDuration(locale, elapsed)}</span>
    </>
  );
}
