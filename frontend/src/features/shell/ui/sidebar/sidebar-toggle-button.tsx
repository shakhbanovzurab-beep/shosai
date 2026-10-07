"use client";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";

import { SidebarToggleIcon } from "./sidebar-toggle-icon";

/** Our sidebar toggle with the custom icon; the arrow appears on hover or keyboard focus. */
export function SidebarToggleButton({ direction, className }: { direction: "close" | "open"; className?: string }) {
  const { toggleSidebar } = useSidebar();
  const t = useTranslations("shell");
  const label = t(direction === "close" ? "sidebar.close" : "sidebar.open");

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      data-sidebar="trigger"
      aria-label={label}
      title={label}
      onClick={toggleSidebar}
      className={cn("group/toggle", className)}
    >
      <SidebarToggleIcon
        direction={direction}
        revealClassName="group-hover/toggle:translate-x-0 group-hover/toggle:opacity-100 group-focus-visible/toggle:translate-x-0 group-focus-visible/toggle:opacity-100"
      />
    </Button>
  );
}
