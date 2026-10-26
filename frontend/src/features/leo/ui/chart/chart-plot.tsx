"use client";

// Модуль грузится только лениво (lazyComponent в leo-artifacts): recharts — в отдельном чанке.
// react-doctor-disable-next-line react-doctor/prefer-dynamic-import
import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartLegend, ChartTooltip } from "@/components/ui/chart";
import { ChartLegendContent } from "@/components/ui/chart-legend";
import { ChartTooltipContent } from "@/components/ui/chart-tooltip";

import type { ChartSpec } from "../../domain/artifacts";
import { formatCategory, formatTick, formatValue, seriesConfig } from "../../domain/chart-values";

/*
 * Сам график: тонкие столбцы до 24px со скруглённым концом или линия в 2px, сплошная сетка в волосок, одна ось
 * значений. Серии по порядку берут цвета темы; при двух и больше — легенда. Наведение показывает все серии точки.
 */

const MARGIN = { top: 8, right: 8, bottom: 0, left: 0 };
// До месяца по дням у каждой точки линии свой маркер; длиннее ряд — только линия.
const MARKED_POINTS = 31;
// Скругляется только конец столбца, у основания он прямой.
const BAR_END: [number, number, number, number] = [4, 4, 0, 0];

function Axes({ x, integers }: { readonly x: string; readonly integers: boolean }) {
  return (
    <>
      <CartesianGrid vertical={false} />
      <XAxis
        dataKey={x}
        tickLine={false}
        axisLine={false}
        tickMargin={8}
        minTickGap={24}
        tickFormatter={formatCategory}
      />
      <YAxis tickLine={false} axisLine={false} width={44} tickFormatter={formatTick} allowDecimals={!integers} />
    </>
  );
}

// Подсказка и легенда идут в порядке серий, а не по алфавиту, как сортирует recharts.
function Tooltip({ cursor, keys }: { readonly cursor: object; readonly keys: readonly string[] }) {
  return (
    <ChartTooltip
      cursor={cursor}
      itemSorter={(item) => keys.indexOf(String(item.dataKey))}
      content={
        <ChartTooltipContent
          indicator="line"
          labelFormatter={(label) => formatCategory(typeof label === "number" ? label : String(label))}
          formatter={(value, name, item) => (
            <div className="flex w-full items-center justify-between gap-4">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <span className="h-2.5 w-1 rounded-full" style={{ background: item.color }} />
                {name}
              </span>
              <span className="font-medium font-mono text-foreground tabular-nums">
                {formatValue(typeof value === "number" ? value : null)}
              </span>
            </div>
          )}
        />
      }
    />
  );
}

/** График по спецификации инструмента; подпись для читалки экрана — заголовок графика. */
export function ChartPlot({ spec, label }: { readonly spec: ChartSpec; readonly label: string }) {
  const config = seriesConfig(spec.series);
  const keys = spec.series.map((series) => series.key);
  const legend = keys.length > 1 ? <ChartLegend itemSorter={null} content={<ChartLegendContent />} /> : null;
  const last = spec.series.length - 1;
  const integers = spec.rows.every((row) => spec.series.every((series) => Number.isInteger(row[series.key] ?? 0)));
  const marked = spec.rows.length <= MARKED_POINTS;
  return (
    <ChartContainer config={config} className="aspect-auto h-52 w-full" role="img" aria-label={label}>
      {spec.shape === "line" ? (
        <LineChart data={spec.rows} margin={MARGIN} accessibilityLayer>
          <Axes x={spec.x} integers={integers} />
          <Tooltip cursor={{ stroke: "var(--border)" }} keys={keys} />
          {legend}
          {spec.series.map((series) => (
            <Line
              key={series.key}
              dataKey={series.key}
              name={series.label}
              // Ломаная, а не сглаживание: между днями значений нет, и рисовать их нечестно.
              type="linear"
              stroke={`var(--color-${series.key})`}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={
                marked
                  ? { r: 4, fill: `var(--color-${series.key})`, stroke: "var(--background)", strokeWidth: 2 }
                  : false
              }
              activeDot={{ r: 4, stroke: "var(--background)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      ) : (
        <BarChart data={spec.rows} margin={MARGIN} accessibilityLayer>
          <Axes x={spec.x} integers={integers} />
          <Tooltip cursor={{ fill: "var(--muted)" }} keys={keys} />
          {legend}
          {spec.series.map((series, index) => (
            <Bar
              key={series.key}
              dataKey={series.key}
              name={series.label}
              stackId={spec.stacked ? "stack" : undefined}
              fill={`var(--color-${series.key})`}
              // Зазор в цвет поверхности разделяет сегменты стопки; отдельные столбцы и так стоят врозь.
              stroke={spec.stacked ? "var(--background)" : undefined}
              strokeWidth={spec.stacked ? 2 : 0}
              maxBarSize={24}
              radius={!spec.stacked || index === last ? BAR_END : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      )}
    </ChartContainer>
  );
}
