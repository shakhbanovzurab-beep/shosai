import type { AiModel } from "./contract";

/* Sortable columns of the models table and how their values compare. */

export type SortKey =
  | "name"
  | "provider"
  | "context_length"
  | "price_input_per_m"
  | "price_output_per_m"
  | "month_spend"
  | "month_requests";
export type Sort = { key: SortKey; desc: boolean };

export const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "name", label: "Модель", numeric: false },
  { key: "provider", label: "Провайдер", numeric: false },
  { key: "context_length", label: "Контекст", numeric: true },
  { key: "price_input_per_m", label: "Вход, 1M", numeric: true },
  { key: "price_output_per_m", label: "Выход, 1M", numeric: true },
  { key: "month_spend", label: "Расход за месяц", numeric: true },
  { key: "month_requests", label: "Запросы", numeric: true },
];

/** Порядок двух моделей по колонке; модель без цены — в конце при любом направлении. */
export function compare(a: AiModel, b: AiModel, { key, desc }: Sort) {
  const left = a[key];
  const right = b[key];
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  const order =
    typeof left === "number" && typeof right === "number"
      ? left - right
      : String(left).localeCompare(String(right), "ru");
  return desc ? -order : order;
}
