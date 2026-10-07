import type { PromoStatus } from "../domain/contract";

/** Badge and dot colours per promo code status; the labels live in `domain/promo-labels.ts`. */
export const STATUS_STYLES: Record<PromoStatus, { badgeClass: string; dotClass: string }> = {
  active: {
    badgeClass: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    dotClass: "bg-emerald-500",
  },
  scheduled: {
    badgeClass: "border-sky-500/20 bg-sky-500/10 text-sky-600 dark:text-sky-400",
    dotClass: "bg-sky-500",
  },
  expired: {
    badgeClass: "border-border bg-muted/50 text-muted-foreground",
    dotClass: "bg-muted-foreground",
  },
  exhausted: {
    badgeClass: "border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    dotClass: "bg-amber-500",
  },
  disabled: {
    badgeClass: "border-destructive/20 bg-destructive/10 text-destructive",
    dotClass: "bg-destructive",
  },
};
