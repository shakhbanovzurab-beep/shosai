import type { ReactNode } from "react";

/** Заголовок формы входа: одна фраза и пояснение под ней. */
export function AuthHeading({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 pb-6">
      <h1 className="font-semibold text-3xl tracking-tight">{title}</h1>
      <p className="text-muted-foreground text-sm">{children}</p>
    </div>
  );
}
