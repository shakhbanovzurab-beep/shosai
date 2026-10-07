import type { ReactNode } from "react";

import { cn } from "cn";

/** The page's width and rhythm, the same as the Meetings page; bottom space keeps clear of the Leo button. */
export function TeamPage({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto flex w-full max-w-6xl flex-col gap-6 pb-16", className)}>{children}</div>;
}

/** The page title, a line on what the page is for, and its main actions on the right. */
export function TeamPageHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="font-semibold text-2xl tracking-tight">{title}</h1>
        {description ? <p className="max-w-2xl text-muted-foreground text-sm">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** A titled block of a page: a small uppercase heading with an optional link or action at the right. */
export function TeamSection({
  id,
  title,
  action,
  children,
  className,
}: {
  id: string;
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-labelledby={id} className={cn("flex min-w-0 flex-col gap-3", className)}>
      <div className="flex min-h-6 items-center justify-between gap-3">
        <h2 id={id} className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A quiet one-line placeholder inside a section that has nothing to show right now. */
export function QuietEmpty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed px-4 py-6 text-center text-muted-foreground text-sm">{children}</p>
  );
}
