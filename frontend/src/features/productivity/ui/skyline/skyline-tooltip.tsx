import type * as React from "react";

import { useTranslations } from "use-intl";

import { useDirection } from "@/components/ui/direction";

import type { Cell } from "../../domain/skyline/contributions";
import type { Formatters } from "../../domain/skyline/format";

/**
 * The active day's count and date. The engine moves it over the cell in the chart's left-to-right frame (its
 * `transform` and the arrow's `--arrow` are measured from the left), so the box stays left to right while its
 * words follow the page direction.
 */
export function SkylineTooltip({
  ref,
  cell,
  fmt,
}: {
  ref: React.Ref<HTMLDivElement>;
  cell: Cell | undefined;
  fmt: Formatters;
}) {
  const t = useTranslations("productivitySkyline");
  const dir = useDirection();
  return (
    <div
      ref={ref}
      role="tooltip"
      aria-hidden={!cell}
      className="pointer-events-none absolute start-3 top-3 z-20 whitespace-nowrap rounded-md bg-foreground px-2.5 py-1.5 text-background text-xs leading-none shadow-lg transition-opacity duration-150 after:absolute after:start-(--arrow) after:top-full after:-ms-1 after:border-4 after:border-transparent after:border-t-foreground motion-reduce:transition-none sm:start-4 sm:top-4"
      style={{ opacity: cell ? 1 : 0 }}
    >
      {cell ? (
        <span dir={dir}>
          {t.rich("tooltip", {
            count: cell.count,
            date: fmt.day(cell.date),
            b: (chunks) => <span className="font-semibold tabular-nums">{chunks}</span>,
          })}
        </span>
      ) : null}
    </div>
  );
}
