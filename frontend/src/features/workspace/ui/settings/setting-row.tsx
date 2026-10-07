import type { ReactNode } from "react";

/** A setting: what it is and what it does on the left, its control on the right (stacked on phones). */
export function SettingRow({
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
    <div className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
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

/** A settings card: a heading, a line on what it covers, and its rows. */
export function SettingsCard({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20 rounded-xl border bg-card">
      <div className="flex flex-col gap-1 border-b px-5 py-4">
        <h2 id={`${id}-title`} className="font-medium">
          {title}
        </h2>
        {description ? <p className="text-muted-foreground text-sm">{description}</p> : null}
      </div>
      <div className="divide-y px-5 py-4">{children}</div>
    </section>
  );
}
