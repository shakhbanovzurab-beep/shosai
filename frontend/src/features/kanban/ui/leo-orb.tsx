"use client";

import { cn } from "cn";

import { attachLeoRing } from "./leo-ring";

/**
 * Знак Leo в Kanban — его кольцо, то же, что встречает человека в чате Leo, и, как там, живое. Все метки доски
 * рисует один общий цикл (`leo-ring`). Смысл знака говорят слова рядом, поэтому для чтения с экрана он скрыт.
 */
export function LeoOrb({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex shrink-0", className)} aria-hidden="true">
      <canvas ref={attachLeoRing} className="size-full" />
    </span>
  );
}
