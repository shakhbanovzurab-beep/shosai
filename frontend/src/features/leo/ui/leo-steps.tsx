"use client";

import * as React from "react";

import { cn } from "cn";
import { Check, ChevronDown, Square, X } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useLocale, useTranslations } from "use-intl";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Spinner } from "@/components/ui/spinner";
import { formatDuration } from "@/i18n/format-units";

import { isLeoActionId, LEO_ACTIONS } from "../domain/actions";
import { getStepsSummary, MIN_VISIBLE_DURATION_MS, type StepsSummary } from "../domain/step-summary";
import type { LeoMessage, LeoStep } from "../domain/types";

export function LeoSteps({ message }: { readonly message: LeoMessage }) {
  const t = useTranslations("leo");
  const steps = message.steps ?? [];
  const isRunning = message.status === "streaming";
  const hasAnswer = message.content.length > 0;

  // Steps stay visible while Leo works and fold away once the answer starts; the user can reopen them.
  const [open, setOpen] = React.useState(!hasAnswer);
  const [prevHasAnswer, setPrevHasAnswer] = React.useState(hasAnswer);
  if (hasAnswer !== prevHasAnswer) {
    setPrevHasAnswer(hasAnswer);
    if (hasAnswer) setOpen(false);
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="group/steps flex items-center gap-1.5 rounded-md text-muted-foreground text-sm outline-none transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
        {isRunning ? (
          <ThinkingOrb state="solving" size={20} aria-hidden="true" />
        ) : (
          <SummaryIcon status={message.status} />
        )}
        <span className={cn(isRunning && "shimmer")} aria-live="polite">
          <SummaryText summary={getStepsSummary(message, steps)} />
        </span>
        <ChevronDown className="size-3.5 transition-transform group-data-[state=open]/steps:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ol className="mt-2 flex flex-col" aria-label={t("steps.label")}>
          {steps.map((step, index) => (
            <StepRow key={step.id} step={step} isLast={index === steps.length - 1} />
          ))}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  );
}

/** The summary line in words: the running action, or how long the reply took and how it ended. */
function SummaryText({ summary }: { readonly summary: StepsSummary }) {
  const t = useTranslations("leo");
  const tActions = useTranslations("leoActions");
  const locale = useLocale();
  switch (summary.kind) {
    case "running":
      return activityLabel(tActions, summary.action);
    case "starting":
      return t("steps.gettingStarted");
    case "stopped":
      return t("steps.stoppedAfter", { duration: formatDuration(locale, summary.ms) });
    case "error":
      return t("steps.somethingWrong");
    default:
      return t("steps.doneIn", { duration: formatDuration(locale, summary.ms) });
  }
}

type ActionsT = ReturnType<typeof useTranslations<"leoActions">>;

/** Слова шага: инструмент или рассуждение по своему коду; код, которого кабинет не знает, — общая строка. */
function activityLabel(tActions: ActionsT, activity: string): string {
  return tActions.has(activity as Parameters<ActionsT>[0])
    ? tActions(activity as Parameters<ActionsT>[0])
    : tActions("generic");
}

function SummaryIcon({ status }: { readonly status: LeoMessage["status"] }) {
  if (status === "error") return <X className="size-3.5 text-destructive" />;
  if (status === "stopped") return <Square className="size-3 fill-current" />;
  return <Check className="size-3.5" />;
}

function StepRow({ step, isLast }: { readonly step: LeoStep; readonly isLast: boolean }) {
  const t = useTranslations("leo");
  const tActions = useTranslations("leoActions");
  const locale = useLocale();
  const action = isLeoActionId(step.action) ? LEO_ACTIONS[step.action] : null;
  const showDuration = step.durationMs !== undefined && step.durationMs >= MIN_VISIBLE_DURATION_MS;
  // What Leo looked for and found is its own text, so it is quoted the language's way and left to set its direction.
  const meta = [step.detail ? t("steps.detail", { detail: step.detail }) : null, step.result]
    .filter(Boolean)
    .join(" · ");

  return (
    <li className="relative flex gap-3 pb-2.5 last:pb-0">
      {!isLast && <span className="absolute start-[7px] top-5 bottom-0 w-px bg-border" aria-hidden="true" />}
      <span className="flex h-5 w-4 shrink-0 items-center justify-center">
        <StepStatusIcon status={step.status} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-baseline justify-between gap-3">
          <span className={cn("text-sm", step.status === "running" ? "text-foreground" : "text-muted-foreground")}>
            {activityLabel(tActions, step.action)}
            {action?.access === "approval" && (
              <span className="ms-1.5 rounded-sm bg-muted px-1 py-0.5 text-[10px] uppercase tracking-wide">
                {t("steps.needsApproval")}
              </span>
            )}
          </span>
          {showDuration && (
            <span className="shrink-0 font-mono text-muted-foreground text-xs tabular-nums">
              {formatDuration(locale, step.durationMs ?? 0)}
            </span>
          )}
        </div>
        {meta ? (
          <span dir="auto" className="truncate text-muted-foreground/80 text-xs">
            {meta}
          </span>
        ) : null}
      </div>
      <span className="sr-only">{t("steps.status", { status: step.status })}</span>
    </li>
  );
}

function StepStatusIcon({ status }: { readonly status: LeoStep["status"] }) {
  switch (status) {
    case "running":
      return <Spinner className="size-3.5 text-muted-foreground" />;
    case "error":
      return <X className="size-3.5 text-destructive" />;
    case "stopped":
      return <Square className="size-2.5 fill-current text-muted-foreground" />;
    default:
      return <Check className="size-3.5 text-green-600 dark:text-green-500" />;
  }
}
