"use client";

import { type ReactNode, useRef } from "react";

import { cn } from "cn";
import { ChevronDown } from "lucide-react";
import { useTranslations } from "use-intl";

import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { TabsTrigger } from "@/components/ui/tabs";

import { EnhancedNotesIcon } from "./enhanced-notes-icon";

interface EnhancedTabProps {
  /** Whether the Enhanced tab is the one showing. */
  readonly active: boolean;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  /** The menu: templates, regenerate, new template. */
  readonly children: ReactNode;
}

/**
 * The Enhanced tab, with its menu in the tab itself: the first click shows the enhanced notes, a click on the
 * tab once it shows (or Arrow Down) opens the templates.
 */
export function EnhancedTab({ active, open, onOpenChange, children }: EnhancedTabProps) {
  const t = useTranslations("notesNote");
  const templateWords = useTranslations("notesTemplates");
  const tabRef = useRef<HTMLButtonElement>(null);
  // Whether the tab was already showing when the click started; the tab activates on mouse down, before the click.
  const wasActive = useRef(false);
  // The tab toggles the menu itself, so pressing it isn't an outside click that closes the menu first.
  const keepOpenOnTab = (event: Event) => {
    if (event.target instanceof Node && tabRef.current?.contains(event.target)) event.preventDefault();
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverAnchor asChild>
        <TabsTrigger
          ref={tabRef}
          value="enhanced"
          className="flex-none"
          aria-haspopup="dialog"
          aria-expanded={open}
          onPointerDown={() => {
            wasActive.current = active;
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") wasActive.current = active;
            if (event.key === "ArrowDown" && active) {
              event.preventDefault();
              onOpenChange(true);
            }
          }}
          onClick={() => {
            if (wasActive.current) onOpenChange(!open);
            wasActive.current = false;
          }}
        >
          <EnhancedNotesIcon />
          {t("tabs.enhanced")}
          <ChevronDown data-icon="inline-end" className={cn("opacity-60 transition-transform", open && "rotate-180")} />
        </TabsTrigger>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        className="w-72 p-0"
        aria-label={templateWords("menu.label")}
        onInteractOutside={keepOpenOnTab}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          tabRef.current?.focus();
        }}
      >
        {children}
      </PopoverContent>
    </Popover>
  );
}
