import { cn } from "cn";
import { ArrowUpRight, Flame, type LucideIcon, Minus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";

import type { Priority } from "../domain/tasks-contract";

const priorityBadgeConfig: Record<
  Priority,
  { icon: LucideIcon; variant: "destructive" | "secondary"; className: string }
> = {
  high: {
    icon: Flame,
    variant: "destructive",
    className: "border-transparent",
  },
  low: {
    icon: Minus,
    variant: "secondary",
    className: "bg-slate-500/10 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300",
  },
  medium: {
    icon: ArrowUpRight,
    variant: "secondary",
    className: "bg-amber-500/10 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  },
};

export function PriorityBadge({ priority, className }: { priority: Priority; className?: string }) {
  const t = useTranslations("kanban");
  const { icon: Icon, variant, className: tone } = priorityBadgeConfig[priority];
  return (
    <Badge variant={variant} className={cn("shrink-0 rounded-md border-transparent px-2 font-medium", tone, className)}>
      {/* Стрелка «средний» поднимается к концу строки, поэтому поворачивается вместе с направлением чтения. */}
      <Icon data-icon="inline-start" className="rtl:-scale-x-100" />
      {t(`priority.${priority}`)}
    </Badge>
  );
}
