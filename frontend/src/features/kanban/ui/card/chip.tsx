import type { ComponentProps, ReactNode } from "react";

import { cn } from "cn";

/** Чип поля на карточке: тихий, или `alert` — для того, что требует решения (просрочено). Прочее — атрибуты чипа. */
export function Chip({
  children,
  tone = "quiet",
  ...attributes
}: { children: ReactNode; tone?: "quiet" | "alert" } & Omit<ComponentProps<"span">, "className" | "children">) {
  return (
    <span
      {...attributes}
      className={cn(
        "inline-flex h-6 min-w-0 max-w-full items-center gap-1 rounded-md border px-1.5 text-xs",
        tone === "alert"
          ? "border-destructive/30 bg-destructive/5 text-destructive"
          : "bg-background text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}
