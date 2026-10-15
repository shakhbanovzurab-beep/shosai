import type { ReactNode } from "react";

/** Заголовок шага входа по центру карточки: одна фраза и пояснение под ней. */
export function AuthHeading({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 pb-6 text-center">
      <h1 className="font-semibold text-2xl tracking-tight">{title}</h1>
      <p className="text-muted-foreground text-sm">{children}</p>
    </div>
  );
}
