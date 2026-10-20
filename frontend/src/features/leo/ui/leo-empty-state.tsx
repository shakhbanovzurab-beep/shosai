"use client";

import * as React from "react";

import { ArrowUpRight } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { hourIn } from "@/i18n/calendar-days";
import { cabinetTimeZone } from "@/i18n/time-zone";

import { adminSuggestions, isAdminPath } from "../domain/admin-suggestions";
import { dayPeriod, SUGGESTION_SLOTS, suggestionSet } from "../domain/suggestions";

// The hour depends on the viewer's clock, so the server renders a neutral fallback.
const getHour = () => hourIn(Date.now(), cabinetTimeZone());

const subscribeToNothing = () => () => undefined;
const getServerHour = (): number | null => null;

interface LeoEmptyStateProps {
  readonly pathname: string;
  /** What Leo can see in the current context. */
  readonly scope: string;
  /** Something worth saying before any question, e.g. a topic going in circles in this hub. */
  readonly notice?: React.ReactNode;
  readonly onSelect: (content: string) => void;
}

export function LeoEmptyState({ pathname, scope, notice, onSelect }: LeoEmptyStateProps) {
  const t = useTranslations("leo");
  const hour = React.useSyncExternalStore<number | null>(subscribeToNothing, getHour, getServerHour);
  const greeting = hour === null ? t("welcome.hi") : t("welcome.greeting", { period: dayPeriod(hour) });

  // The admin panel is Russian only, so its questions aren't in the catalogs.
  const set = suggestionSet(pathname);
  const suggestions = isAdminPath(pathname)
    ? adminSuggestions(pathname)
    : SUGGESTION_SLOTS.map((slot) => t(`suggestions.${set}.${slot}`));

  return (
    <div className="flex min-h-0 flex-1 flex-col justify-end gap-6 overflow-y-auto px-4 pt-8 pb-2 group-data-[expanded=true]/leo:mx-auto group-data-[expanded=true]/leo:w-full group-data-[expanded=true]/leo:max-w-3xl group-data-[expanded=true]/leo:justify-center">
      <div className="flex flex-col items-start gap-3">
        <span className="flex [&_canvas]:size-12!" aria-hidden="true">
          <ThinkingOrb state="breathing" size={64} />
        </span>
        <div className="flex flex-col gap-1">
          <p className="font-medium text-xl tracking-tight">{t("welcome.intro", { greeting })}</p>
          <p className="text-muted-foreground text-sm">{t("welcome.howCanIHelp")}</p>
          <p className="text-muted-foreground text-xs">{scope}</p>
        </div>
      </div>
      {notice}
      <ul className="flex flex-col gap-1.5" aria-label={t("welcome.suggestionsLabel")}>
        {suggestions.map((suggestion) => (
          <li key={suggestion}>
            <button
              type="button"
              onClick={() => onSelect(suggestion)}
              className="group flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-start text-sm outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {suggestion}
              <ArrowUpRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 ltr:group-hover:translate-x-0.5 rtl:-scale-x-100 rtl:group-hover:-translate-x-0.5" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
