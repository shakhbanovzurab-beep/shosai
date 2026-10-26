import type { ChartSeries, ChartSpec } from "./artifacts";

/*
 * Подписи и цвета графика Leo. Графики бывают только у оператора в админ-панели, а она только на русском
 * (docs/i18n.md): числа и даты пишутся по-русски. Строки графика посчитал инструмент; здесь их только называют.
 */

// Категориальные цвета темы по порядку серий, без повторов: серий у инструментов платформы не больше двух.
const SERIES_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

const NUMBER = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
const COMPACT = new Intl.NumberFormat("ru-RU", { notation: "compact", maximumFractionDigits: 1 });
const DAY = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", timeZone: "UTC" });

export type ChartCell = ChartSpec["rows"][number][string];

/** Значение ячейки: число по-русски, пустое — тире. */
export function formatValue(value: ChartCell | undefined): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "number" ? NUMBER.format(value) : value;
}

/** Деление оси значений: 0, 950, 1,2 тыс. */
export const formatTick = (value: number): string => COMPACT.format(value);

/** Подпись по оси x: день — «26 окт.», остальное как есть. */
export function formatCategory(value: ChartCell | undefined): string {
  if (typeof value === "string" && ISO_DAY.test(value)) return DAY.format(new Date(`${value}T00:00:00Z`));
  return formatValue(value);
}

/** Цвет серии по её месту в спецификации: он следует за серией, а не за её величиной. */
export const seriesColor = (index: number): string => SERIES_COLORS[index] ?? "var(--muted-foreground)";

/** Конфигурация shadcn-графика: подпись и цвет каждой серии. */
export function seriesConfig(series: readonly ChartSeries[]) {
  return Object.fromEntries(series.map((item, index) => [item.key, { label: item.label, color: seriesColor(index) }]));
}
