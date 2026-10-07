import { cn } from "cn";
import { ArrowUpRight, Flame, type LucideIcon, Minus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";

import type { TaskPriority } from "../domain/board";
import { PRIORITY_KEYS } from "./priority-keys";

const priorityBadgeConfig: Record<
  TaskPriority,
  { icon: LucideIcon; variant: "destructive" | "secondary"; className: string }
> = {
  High: {
    icon: Flame,
    variant: "destructive",
    className: "border-transparent",
  },
  Low: {
    icon: Minus,
    variant: "secondary",
    className: "bg-slate-500/10 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300",
  },
  Medium: {
    icon: ArrowUpRight,
    variant: "secondary",
    className: "bg-amber-500/10 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  },
};

export function PriorityBadge({ priority, className }: { priority: TaskPriority; className?: string }) {
  const t = useTranslations("kanban");
  const { icon: Icon, variant, className: tone } = priorityBadgeConfig[priority];
  return (
    <Badge variant={variant} className={cn("shrink-0 rounded-md border-transparent px-2 font-medium", tone, className)}>
      {/* The Medium arrow rises towards the end of the line, so it turns with the reading direction. */}
      <Icon data-icon="inline-start" className="rtl:-scale-x-100" />
      {t(`priority.${PRIORITY_KEYS[priority]}`)}
    </Badge>
  );
}
