"use client";

import Link from "next/link";

import { cn } from "cn";
import { Circle, CircleCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useDismissed } from "@/hooks/use-dismissed";

import type { SetupStep, SetupStepId } from "../../domain/setup";
import { openInviteDialog } from "../../model/invite-dialog-store";
import { useWorkspace } from "../../model/use-workspace";

// Where each step is done; inviting opens the dialog instead.
const PATHS: Record<SetupStepId, string | null> = {
  invite: null,
  sharing: "/settings#sharing",
  share: "/meetings",
  knowledge: "/knowledge",
};

/** A step's button: a link to where it's done, or the invite dialog. */
function StepAction({ id }: { id: SetupStepId }) {
  const t = useTranslations("workspaceHome");
  const { path } = useWorkspace();
  const to = PATHS[id];
  const label = t(`setup.steps.${id}.action`);
  if (!to)
    return (
      <Button size="sm" variant="outline" className="ms-8 sm:ms-0" onClick={openInviteDialog}>
        {label}
      </Button>
    );
  return (
    <Button asChild size="sm" variant="outline" className="ms-8 sm:ms-0">
      <Link href={path(to)}>{label}</Link>
    </Button>
  );
}

/** The first steps of a new workspace; it goes away once they're done, or when dismissed. */
export function SetupChecklist({ steps }: { steps: SetupStep[] }) {
  const t = useTranslations("workspaceHome");
  const { ws } = useWorkspace();
  const [dismissed, dismiss] = useDismissed(`workspace-setup-dismissed:${ws}`);
  const done = steps.filter((s) => s.done).length;
  if (dismissed || done === steps.length) return null;

  return (
    <section aria-labelledby="setup-title" className="flex flex-col gap-4 rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 id="setup-title" className="font-medium">
            {t("setup.title")}
          </h2>
          <p className="text-muted-foreground text-sm">{t("setup.progress", { done, total: steps.length })}</p>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label={t("setup.hide")} onClick={dismiss}>
          <X />
        </Button>
      </div>
      <Progress
        value={(done / steps.length) * 100}
        aria-label={t("setup.progressLabel", { done, total: steps.length })}
      />
      <ol className="flex flex-col divide-y">
        {steps.map((step) => {
          return (
            <li key={step.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3 first:pt-1 last:pb-0">
              {step.done ? (
                <CircleCheck className="size-5 shrink-0 text-primary" aria-label={t("setup.done")} />
              ) : (
                <Circle className="size-5 shrink-0 text-muted-foreground" aria-label={t("setup.toDo")} />
              )}
              <div className="flex min-w-0 flex-1 basis-56 flex-col">
                <span className={cn("font-medium text-sm", step.done && "text-muted-foreground line-through")}>
                  {t(`setup.steps.${step.id}.title`)}
                </span>
                {step.done ? null : (
                  <span className="text-muted-foreground text-sm">{t(`setup.steps.${step.id}.description`)}</span>
                )}
              </div>
              {step.done ? null : <StepAction id={step.id} />}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
