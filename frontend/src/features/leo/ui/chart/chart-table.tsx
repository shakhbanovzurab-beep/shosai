import type { ChartSpec } from "../../domain/artifacts";
import { formatCategory, formatValue } from "../../domain/chart-values";

/** Те же строки таблицей: каждое значение графика читается без наведения и без цвета. */
export function ChartTable({ spec, caption }: { readonly spec: ChartSpec; readonly caption: string }) {
  return (
    <div className="max-h-64 overflow-auto rounded-md border">
      <table className="w-full text-xs">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-background">
          <tr className="border-b">
            <td />
            {spec.series.map((series) => (
              <th key={series.key} scope="col" className="px-2 py-1.5 text-end font-medium text-muted-foreground">
                {series.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.rows.map((row) => {
            const category = formatCategory(row[spec.x]);
            return (
              <tr key={String(row[spec.x])} className="border-b last:border-0">
                <th scope="row" className="max-w-40 truncate px-2 py-1.5 text-start font-normal" title={category}>
                  {category}
                </th>
                {spec.series.map((series) => (
                  <td key={series.key} className="px-2 py-1.5 text-end tabular-nums">
                    {formatValue(row[series.key])}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
