import type { ReactNode } from "react";

/** Строка поля в панели: название слева, значение и его управление справа; на телефоне — одно под другим. */
export function FieldRow({ label, labelId, children }: { label: string; labelId: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 items-start gap-1 sm:grid-cols-[10rem_1fr] sm:gap-3">
      <dt id={labelId} className="pt-1.5 text-muted-foreground text-sm">
        {label}
      </dt>
      <dd className="flex min-w-0 flex-wrap items-center gap-2">{children}</dd>
    </div>
  );
}
