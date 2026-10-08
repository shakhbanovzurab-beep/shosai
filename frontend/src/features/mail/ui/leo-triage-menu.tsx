"use client";

import { ChevronDown } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem } from "@/components/ui/dropdown-menu-items";

import { MAIL_TRIAGES } from "../domain/leo-insights";
import type { LeoMailView } from "../domain/leo-triage";
import { leoActions } from "../model/leo-store";

/** How Leo sorted the email, as a menu to re-sort it when Leo got it wrong. */
export function LeoTriageMenu({ mailId, view }: { mailId: string; view: LeoMailView }) {
  const t = useTranslations("mailLeo");
  if (!view.triage) return null;
  const label = t(`triage.${view.triage}`);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="xs" aria-label={t("triageMenu.trigger", { triage: label })}>
          {label}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            {view.isCorrected ? t("triageMenu.sortedByYou") : t("triageMenu.sortedByLeo")}
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={view.triage}
            onValueChange={(value) => {
              const triage = MAIL_TRIAGES.find((option) => option === value);
              if (triage) leoActions.correctTriage(mailId, triage, view.insight.triage);
            }}
          >
            {MAIL_TRIAGES.map((option) => (
              <DropdownMenuRadioItem key={option} value={option}>
                <div className="flex min-w-0 flex-col">
                  <span>{t(`triage.${option}`)}</span>
                  <span className="text-muted-foreground text-xs">
                    {view.isCorrected && option === view.insight.triage
                      ? t("triageMenu.leosPick", { hint: t(`triageHint.${option}`) })
                      : t(`triageHint.${option}`)}
                  </span>
                </div>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
