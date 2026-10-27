"use client";

import { Brain, CornerDownRight, RefreshCw } from "lucide-react";
import { useTranslations } from "use-intl";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia } from "@/components/ui/empty";
import type { MemorySummary } from "@/features/memory/domain/summary-contract";

/** What Leo wrote: its sections and suggested questions, each in the direction of its own text. */
export function MemorySummaryBody({
  summary,
  onSuggest,
}: {
  summary: MemorySummary;
  onSuggest: (text: string) => void;
}) {
  const t = useTranslations("settingsMemory");
  if (summary.sections.length === 0)
    return (
      <Empty className="min-h-56">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Brain />
          </EmptyMedia>
          <EmptyDescription>{t("summary.empty")}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  return (
    <div className="flex flex-col gap-6">
      {summary.stale ? (
        <p role="status" className="flex items-center gap-2 text-muted-foreground text-sm">
          <RefreshCw className="size-3.5 shrink-0" aria-hidden="true" />
          {t("summary.stale")}
        </p>
      ) : null}
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
