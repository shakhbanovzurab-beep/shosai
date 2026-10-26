"use client";

import type * as React from "react";

import { cn } from "cn";
import { BookOpen, Globe, Search, Square, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { formatDuration } from "@/i18n/format-units";

import { isLeoActionId, LEO_ACTIONS } from "../domain/actions";
import { stepMark } from "../domain/step-marks";
import { MIN_VISIBLE_DURATION_MS } from "../domain/step-summary";
import type { LeoMessage, LeoStep } from "../domain/types";
import { LeoStepSources } from "./leo-step-sources";

type ActionsT = ReturnType<typeof useTranslations<"leoActions">>;

/** Слова шага: инструмент или рассуждение по своему коду; код, которого кабинет не знает, — общая строка. */
function activityLabel(tActions: ActionsT, activity: string): string {
  return tActions.has(activity as Parameters<ActionsT>[0])
    ? tActions(activity as Parameters<ActionsT>[0])
    : tActions("generic");
}

/** Лента хода: шаги по порядку, найденные источники и итог; узлы соединены тонкой линией. */
export function LeoStepsTimeline({ message, steps }: { readonly message: LeoMessage; readonly steps: LeoStep[] }) {
  const t = useTranslations("leo");
  const isRunning = message.status === "streaming";
  const sources = message.sources ?? [];

  return (
    <ol aria-label={t("steps.label")} aria-live="polite" className="mt-3 flex flex-col">
      {steps.map((step) => (
        <StepRow key={step.id} step={step} />
      ))}
      {sources.length > 0 ? (
        <Row mark={<BookOpen className="size-3.5 text-muted-foreground" />}>
          <LeoStepSources sources={sources} />
        </Row>
      ) : null}
      {isRunning ? <IdleRow message={message} steps={steps} /> : <FinalRow status={message.status} />}
    </ol>
  );
}

function Row({ mark, children }: { readonly mark: React.ReactNode; readonly children: React.ReactNode }) {
  return (
    <li className="group/row fade-in slide-in-from-bottom-1 relative flex animate-in gap-3 pb-3 duration-300 last:pb-0 motion-reduce:animate-none">
      <span
        aria-hidden="true"
        className="absolute start-[7.5px] top-[19px] -bottom-px w-px bg-border group-last/row:hidden"
      />
      <span aria-hidden="true" className="flex h-5 w-4 shrink-0 items-center justify-center">
        {mark}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">{children}</div>
    </li>
  );
}

/** Узел идущего шага: пульсирующая синяя точка, как на всех лентах работы Leo. */
const ACTIVE_MARK = <span className="size-2 animate-pulse rounded-[2px] bg-blue-500 motion-reduce:animate-none" />;

function StepRow({ step }: { readonly step: LeoStep }) {
  const t = useTranslations("leo");
  const tActions = useTranslations("leoActions");
  const locale = useLocale();
  const action = isLeoActionId(step.action) ? LEO_ACTIONS[step.action] : null;
  const showDuration = step.durationMs !== undefined && step.durationMs >= MIN_VISIBLE_DURATION_MS;
  // Что Leo искал и что нашёл — его собственный текст: в кавычках языка и со своим направлением.
  const meta = [step.detail ? t("steps.detail", { detail: step.detail }) : null, step.result]
    .filter(Boolean)
    .join(" · ");

  return (
    <Row mark={<StepMark step={step} />}>
      <div className="flex items-baseline justify-between gap-3">
        <span className={cn("text-sm", step.status === "running" ? "shimmer" : "text-muted-foreground")}>
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
        <span dir="auto" className="-mt-1 truncate text-muted-foreground/80 text-xs">
          {meta}
        </span>
      ) : null}
      <span className="sr-only">{t("steps.status", { status: step.status })}</span>
    </Row>
  );
}

function StepMark({ step }: { readonly step: LeoStep }) {
  if (step.status === "running") return ACTIVE_MARK;
  if (step.status === "error") return <X className="size-3.5 text-destructive" />;
  if (step.status === "stopped") return <Square className="size-2.5 fill-current text-muted-foreground" />;
  const mark = stepMark(step.action);
  if (mark === "web") return <Globe className="size-3.5 text-muted-foreground" />;
  if (mark === "search") return <Search className="size-3.5 text-muted-foreground" />;
  return <span className="size-1.5 rounded-full bg-muted-foreground/50" />;
}

/** Ход идёт, а шага нет: Leo начинает, думает между шагами или пишет ответ. */
function IdleRow({ message, steps }: { readonly message: LeoMessage; readonly steps: LeoStep[] }) {
  const t = useTranslations("leo");
  const tActions = useTranslations("leoActions");
  if (steps.some((step) => step.status === "running")) return null;
  let label = t("steps.gettingStarted");
  if (message.content.length > 0) label = tActions("write_answer");
  else if (steps.length > 0) label = tActions("think");
  return (
    <Row mark={ACTIVE_MARK}>
      <span className="shimmer text-sm">{label}</span>
    </Row>
  );
}

function FinalRow({ status }: { readonly status: LeoMessage["status"] }) {
  const t = useTranslations("leo");
  // Сбой называет блок ошибки под заголовком, остановку — сам заголовок; итог нужен только готовому ответу.
  if (status !== "done") return null;
  return (
    <Row mark={<FinishedMark />}>
      <span className="text-foreground text-sm">{t("steps.finished")}</span>
    </Row>
  );
}

function FinishedMark() {
  return (
    <span className="zoom-in-50 flex size-4 animate-in items-center justify-center rounded-full bg-blue-500 text-white duration-300 motion-reduce:animate-none">
      <svg viewBox="0 0 16 16" className="size-3" fill="none" aria-hidden="true">
        <path
          d="M4.5 8.5l2.25 2.25L11.5 6"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray={1}
          className="animate-draw motion-reduce:animate-none"
        />
      </svg>
    </span>
  );
}
