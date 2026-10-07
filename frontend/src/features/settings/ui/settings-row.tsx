import type { ReactNode } from "react";

/** A setting: what it is and what it does on the left, its control on the right. */
export function SettingsRow({
  title,
  description,
  htmlFor,
  children,
}: {
  title: string;
  description?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
      <div className="flex min-w-0 flex-col gap-1">
        <label htmlFor={htmlFor} className="font-medium text-sm">
          {title}
        </label>
        {description ? <p className="text-muted-foreground text-sm">{description}</p> : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

/** A titled group of rows inside a section. */
export function SettingsGroup({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col">
      {title ? <h3 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">{title}</h3> : null}
      <div className="divide-y">{children}</div>
    </section>
  );
}
