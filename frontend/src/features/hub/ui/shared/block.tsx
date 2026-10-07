import type { ReactNode } from "react";

import { cn } from "cn";
import { CircleAlert, RotateCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

/* The quiet frame of a reading screen: a section with a small heading, and its partial and error notes. */

export function Block({
  id,
  title,
  aside,
  children,
  className,
}: {
  id: string;
  title: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-labelledby={id} className={cn("flex min-w-0 flex-col gap-3", className)}>
      <div className="flex min-h-7 flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h2 id={id} className="font-medium text-muted-foreground text-sm">
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** "Some of this didn't load", with a retry; what did load stays on screen. */
export function PartialNote({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-muted-foreground text-xs" role="status">
      <CircleAlert className="size-3.5 shrink-0" aria-hidden="true" />
      {t("partial")}
      <Button variant="ghost" size="xs" className="h-6 border-border bg-transparent" onClick={onRetry}>
        <RotateCw data-icon="inline-start" />
        {common("actions.retry")}
      </Button>
    </p>
  );
}

/** A block that couldn't load: what failed, in words, and a way to try again. */
export function BlockError({
  title,
  description,
  onRetry,
}: {
  title: string;
  description?: string;
  onRetry: () => void;
}) {
  const common = useTranslations("common");
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed bg-transparent px-4 py-3"
    >
      <div className="flex min-w-0 items-start gap-2 text-sm">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0">
          <p className="font-medium">{title}</p>
          {description ? <p className="text-muted-foreground text-xs">{description}</p> : null}
        </div>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {common("actions.retry")}
      </Button>
    </div>
  );
}

/** A quiet, deliberately designed "nothing here" line: a valid answer, not an error. */
export function QuietEmpty({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 rounded-lg border border-dashed bg-transparent px-4 py-4 text-muted-foreground text-sm">
      {icon}
      {children}
    </p>
  );
}
