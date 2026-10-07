import type { ComponentType, ReactNode } from "react";

import { cn } from "cn";

/**
 * A value in a row of facts that acts (opens a picker, files somewhere): on a ghost `xs` Button it reads
 * like the plain values beside it until hovered. The negative margins keep its text, and the gaps around
 * it, where a plain value's would be; `text-sm` overrides the button size's `text-xs`; it may shrink, so text inside should truncate.
 */
export const META_VALUE_BUTTON =
  "-mx-1.5 h-6 min-w-0 shrink gap-1.5 px-1.5 font-normal text-muted-foreground text-sm hover:text-foreground";

interface MetaItemProps {
  /** Left out when the value draws its own icon, e.g. a button with an icon and a count. */
  readonly icon?: ComponentType<{ className?: string }>;
  /** What the value is, for screen readers. */
  readonly label: string;
  readonly className?: string;
  readonly children: ReactNode;
}

/** One fact in a `dl` row of facts, such as the row under a note's title: an icon and the value. */
export function MetaItem({ icon: Icon, label, className, children }: MetaItemProps) {
  return (
    <div className={cn("flex min-w-0 items-center gap-1.5", className)}>
      <dt className="sr-only">{label}</dt>
      {Icon ? <Icon className="size-4 shrink-0" aria-hidden="true" /> : null}
      <dd className="flex min-w-0 items-center gap-1">{children}</dd>
    </div>
  );
}
