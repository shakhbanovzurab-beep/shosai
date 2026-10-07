import { cn } from "cn";
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";

import type { ThreadStage, ThreadTransition } from "../../domain/contract";
import { STAGE_PATH } from "../../domain/urgency";
import { useHubPhrases } from "../shared/phrases";

/** When a stage was reached: the first time for a passed stage, the latest for the current one. */
const reachedAt = (transitions: ThreadTransition[], stage: ThreadStage, current: boolean) =>
  (current ? transitions.findLast((t) => t.to === stage) : transitions.find((t) => t.to === stage))?.at;

/**
 * raised → under discussion → decided → in progress → closed (or abandoned). Stages passed show
 * their date; the current one stands out by weight and a ring, not by colour alone.
 */
export function StageTrack({ stage, transitions }: { stage: ThreadStage; transitions: ThreadTransition[] }) {
  const t = useTranslations("hubDetail");
  const hubWords = useTranslations("hub");
  const say = useHubPhrases();
  const path: ThreadStage[] = stage === "abandoned" ? [...STAGE_PATH.slice(0, -1), "abandoned"] : [...STAGE_PATH];
  const current = path.indexOf(stage);
  return (
    <ol className="grid grid-cols-5 gap-1" aria-label={t("thread.stages")}>
      {path.map((step, index) => {
        const passed = index < current;
        const here = index === current;
        const date = reachedAt(transitions, step, here);
        return (
          <li key={step} className="flex min-w-0 flex-col gap-1.5" aria-current={here ? "step" : undefined}>
            <span
              className={cn(
                "flex h-1.5 rounded-full",
                passed || here ? "bg-foreground/70" : "bg-border",
                here && "ring-2 ring-foreground/20 ring-offset-1 ring-offset-background",
              )}
              aria-hidden="true"
            />
            <span
              className={cn(
                "flex items-start gap-1 text-pretty text-[11px] leading-tight sm:text-xs",
                here ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {passed ? <Check className="mt-px size-3 shrink-0" aria-hidden="true" /> : null}
              <span className="min-w-0">{hubWords(`stage.${step}`)}</span>
            </span>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {date && (passed || here) ? say.date(date) : " "}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
