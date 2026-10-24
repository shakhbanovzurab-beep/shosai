"use client";

import type * as React from "react";

import { cn } from "cn";
import { AnimatePresence, m } from "framer-motion";
import { Maximize, Minimize, Plus, X } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface LeoPanelHeaderProps {
  readonly isBusy: boolean;
  /** Где работает Leo («Personal», «In Lumen»), под заголовком, пока он не занят. */
  readonly placeLabel: string;
  readonly expanded: boolean;
  readonly canReset: boolean;
  readonly onReset: () => void;
  /** Что ещё стоит рядом с «Новым чатом»: меню «Недавние чаты» у Leo на API. */
  readonly beside?: React.ReactNode;
  readonly onToggleExpanded: () => void;
  readonly onClose: () => void;
}

/** Шапка панели Leo: новый чат, сфера с заголовком посередине, полный экран и закрытие. */
export function LeoPanelHeader({
  isBusy,
  placeLabel,
  expanded,
  canReset,
  onReset,
  beside,
  onToggleExpanded,
  onClose,
}: LeoPanelHeaderProps) {
  const t = useTranslations("leo");
  return (
    <m.header layout="position" className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-2 py-2.5">
      <div className="flex items-center">
        <HeaderAction label={t("panel.newChat")} onClick={onReset} disabled={!canReset}>
          <Plus />
        </HeaderAction>
        {beside}
      </div>
      {/* The orb hangs off the left edge so the title itself sits exactly in the middle. */}
      <div className="relative flex flex-col items-center text-center">
        <span className="absolute end-full top-1/2 me-2.5 flex -translate-y-1/2 [&_canvas]:size-8!" aria-hidden="true">
          <ThinkingOrb state={isBusy ? "solving" : "breathing"} size={32} />
        </span>
        <h2 className="font-medium text-sm leading-none">Leo</h2>
        <p className="mt-1 whitespace-nowrap text-muted-foreground text-xs leading-none">
          {isBusy ? t("panel.working") : placeLabel}
        </p>
      </div>
      <div className="flex items-center justify-end gap-0.5">
        <HeaderAction label={expanded ? t("panel.exitFullScreen") : t("panel.fullScreen")} onClick={onToggleExpanded}>
          <AnimatePresence mode="popLayout" initial={false}>
            <m.span
              key={expanded ? "minimize" : "maximize"}
              className="flex"
              initial={{ opacity: 0, rotate: -90, scale: 0.5 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: 90, scale: 0.5 }}
              transition={{ duration: 0.2 }}
            >
              {expanded ? <Minimize /> : <Maximize />}
            </m.span>
          </AnimatePresence>
        </HeaderAction>
        <HeaderAction label={t("panel.close")} onClick={onClose}>
          <X />
        </HeaderAction>
      </div>
    </m.header>
  );
}

function HeaderAction({
  label,
  className,
  ...props
}: React.ComponentProps<typeof Button> & { readonly label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          className={cn("text-muted-foreground", className)}
          {...props}
        />
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
