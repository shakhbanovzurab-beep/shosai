import type { SVGProps } from "react";

import { cn } from "cn";

/**
 * Знак Shosai: две створки сёдзи, передняя отъехала и наехала на заднюю — вход в кабинет.
 * Поля обрезаны до 2 единиц, чтобы знак читался крупно в одном ряду с плиткой пространства.
 * Цвет — `currentColor`. Исходники — `docs/brand/`.
 */
export function ShosaiMark({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="4 4 56 56"
      width="24"
      height="24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      className={cn("shrink-0", className)}
      {...props}
    >
      <path d="M12 5H26.86A10 10 0 0 0 24 12V52A10 10 0 0 0 26.86 59H12A7 7 0 0 1 5 52V12A7 7 0 0 1 12 5Z" />
      <path d="M34 5H52A7 7 0 0 1 59 12V52A7 7 0 0 1 52 59H34A7 7 0 0 1 27 52V12A7 7 0 0 1 34 5Z" />
    </svg>
  );
}
