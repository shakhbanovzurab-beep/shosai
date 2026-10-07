import { CircleCheck, CirclePause, CreditCard, Hourglass, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";

import type { WorkspaceStatus } from "../domain/contract";
import { STATUS_LABEL } from "../domain/labels";

/** Colour only where it calls for action, always with its icon and label. */
const STYLE: Record<WorkspaceStatus, { icon: LucideIcon; className?: string; variant?: "outline" }> = {
  active: { icon: CircleCheck, variant: "outline" },
  trialing: { icon: Hourglass, className: "bg-sky-500/10 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
  past_due: {
    icon: CreditCard,
    className: "bg-amber-500/10 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  },
  suspended: { icon: CirclePause, className: "bg-red-500/10 text-red-700 dark:bg-red-500/15 dark:text-red-300" },
};

export function StatusBadge({ status }: { status: WorkspaceStatus }) {
  const { icon: Icon, className, variant } = STYLE[status];
  return (
    <Badge variant={variant} className={className}>
      <Icon aria-hidden="true" className={status === "active" ? "text-emerald-600 dark:text-emerald-400" : undefined} />
      {STATUS_LABEL[status]}
    </Badge>
  );
}
