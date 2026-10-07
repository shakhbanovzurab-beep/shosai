import { CircleCheck, CircleX, Clock, type LucideIcon, Undo2 } from "lucide-react";

import type { TransactionStatus } from "../domain/contract";

/** Status colors are reserved for payment state and always come with an icon and a label. */
export const STATUS_STYLES: Record<TransactionStatus, { icon: LucideIcon; swatch: string; badge: string }> = {
  paid: {
    icon: CircleCheck,
    swatch: "bg-green-500",
    badge:
      "border-green-200 bg-green-500/10 text-green-700 dark:border-green-900/40 dark:bg-green-500/15 dark:text-green-300",
  },
  pending: {
    icon: Clock,
    swatch: "bg-amber-500",
    badge:
      "border-amber-200 bg-amber-500/10 text-amber-700 dark:border-amber-900/40 dark:bg-amber-500/15 dark:text-amber-300",
  },
  failed: {
    icon: CircleX,
    swatch: "bg-destructive",
    badge: "border-destructive/20 bg-destructive/10 text-destructive",
  },
  refunded: {
    icon: Undo2,
    swatch: "bg-muted-foreground",
    badge: "border-border bg-muted text-muted-foreground",
  },
};
