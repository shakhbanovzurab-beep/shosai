import { pluralizeRu } from "@/lib/plural";

import type { Transaction } from "../domain/contract";
import { formatDay, formatMoney } from "../domain/format";
import { PLAN_LABELS, paymentMethodLabel, STATUS_LABELS } from "../domain/labels";

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const UNSAFE = /[&<>"']/g;
const escapeHtml = (value: string) => value.replace(UNSAFE, (char) => ESCAPES[char] ?? char);

/** A printable HTML invoice for the demo, in the payment's currency; the real backend serves a PDF. */
export function renderInvoice(transaction: Transaction) {
  const plan = PLAN_LABELS[transaction.plan];
  const seats =
    transaction.seats === null
      ? ""
      : `, ${transaction.seats} ${pluralizeRu(transaction.seats, ["место", "места", "мест"])}`;
  const money = (minor: number) => formatMoney(minor, transaction.currency);
  const rows: [string, string][] = [
    ["Дата", formatDay(transaction.created_at)],
    ["Плательщик", `${transaction.customer.name}, ${transaction.customer.email}`],
    ["Услуга", `Подписка Leo ${plan}${seats}, 1 мес.`],
    ["Сумма", money(transaction.amount_minor)],
    ["Способ оплаты", paymentMethodLabel(transaction.method)],
    ["Статус", STATUS_LABELS[transaction.status]],
  ];
  if (transaction.refunded_minor > 0) rows.push(["Возвращено", money(transaction.refunded_minor)]);
  const body = rows
    .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");
  const number = escapeHtml(transaction.number);
  return `<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Счёт ${number}</title>
<style>body{font:14px/1.5 system-ui,sans-serif;margin:40px;color:CanvasText}th{text-align:left;padding:4px 24px 4px 0;font-weight:500;color:GrayText}</style>
</head><body><h1>Счёт № ${number}</h1><p>Leo · демо-счёт, без НДС</p><table>${body}</table></body></html>`;
}
