import type { ReactNode } from "react";

import type { ChartConfig } from "@/components/ui/chart";

type TooltipIndicator = "dot" | "line";

type TooltipItem = {
  color?: string;
  payload?: { fill?: string };
};

export function createTooltipFormatter(
  config: ChartConfig,
  formatValue: (value: number) => string,
  indicator: TooltipIndicator = "dot",
) {
  return function tooltipFormatter(value: unknown, name: unknown, item: TooltipItem): ReactNode {
    const key = String(name);
    const label = config[key]?.label ?? key;
    const indicatorColor = item.payload?.fill ?? item.color;
    const numericValue = typeof value === "number" ? value : Number(value);

    return (
      <>
        <div
          className={indicator === "dot" ? "size-2.5 shrink-0 rounded-[2px]" : "w-1 shrink-0 rounded-[2px]"}
          style={{ backgroundColor: indicatorColor }}
        />
        <div className="flex flex-1 items-center justify-between gap-2 leading-none">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium font-mono text-foreground tabular-nums">
            {Number.isFinite(numericValue) ? formatValue(numericValue) : String(value)}
          </span>
        </div>
      </>
    );
  };
}
