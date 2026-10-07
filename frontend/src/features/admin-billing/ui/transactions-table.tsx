import { CreditCard, Download, Landmark, Smartphone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { pluralizeRu } from "@/lib/plural";

import type { Transaction, TransactionPaymentMethod } from "../domain/contract";
import { formatDay, formatMoney, formatTime } from "../domain/format";
import { PLAN_LABELS, paymentMethodLabel } from "../domain/labels";
import { StatusBadge } from "./status-badge";
import { TransactionActions } from "./transaction-actions";

const SEAT_WORDS = ["место", "места", "мест"] as const;
const METHOD_ICONS = { card: CreditCard, sbp: Smartphone, bank_transfer: Landmark } as const;

function MethodCell({ method }: { method: TransactionPaymentMethod }) {
  const Icon = METHOD_ICONS[method.type];
  return (
    <span className="flex items-center gap-2">
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="truncate">{paymentMethodLabel(method)}</span>
    </span>
  );
}

const HEADERS = ["Дата", "Клиент", "Тариф", "Сумма", "Способ оплаты", "Статус", "Счёт"] as const;

function Head() {
  return (
    <TableHeader className="[&_tr]:border-t">
      <TableRow>
        {HEADERS.map((label) => (
          <TableHead key={label} className={label === "Сумма" ? "py-3 text-right font-normal" : "py-3 font-normal"}>
            {label}
          </TableHead>
        ))}
        <TableHead className="w-12 py-3">
          <span className="sr-only">Действия</span>
        </TableHead>
      </TableRow>
    </TableHeader>
  );
}

const TABLE_CLASS = "min-w-[64rem] **:data-[slot='table-cell']:px-4 **:data-[slot='table-head']:px-4";

export function TransactionsTable({
  items,
  busy,
  onRefund,
}: {
  items: Transaction[];
  busy: boolean;
  onRefund: (transaction: Transaction) => void;
}) {
  return (
    <Table className={TABLE_CLASS} aria-busy={busy} aria-label="Платежи">
      <Head />
      <TableBody className={busy ? "opacity-60 transition-opacity" : "transition-opacity"}>
        {items.map((transaction) => (
          <TableRow key={transaction.id} className="border-border/60">
            <TableCell className="py-3">
              <div className="flex flex-col gap-0.5 whitespace-nowrap">
                <time dateTime={transaction.created_at}>{formatDay(transaction.created_at)}</time>
                <span className="text-muted-foreground text-xs tabular-nums">
                  {formatTime(transaction.created_at)} UTC
                </span>
              </div>
            </TableCell>
            <TableCell className="max-w-64 py-3">
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate font-medium" title={transaction.customer.name}>
                  {transaction.customer.name}
                </span>
                <span className="truncate text-muted-foreground text-xs" title={transaction.customer.email}>
                  {transaction.customer.email}
                </span>
              </div>
            </TableCell>
            <TableCell className="py-3">
              <div className="flex flex-col items-start gap-0.5">
                <Badge variant="outline" className="rounded-md">
                  {PLAN_LABELS[transaction.plan]}
                </Badge>
                {transaction.seats === null ? null : (
                  <span className="text-muted-foreground text-xs tabular-nums">
                    {transaction.seats} {pluralizeRu(transaction.seats, SEAT_WORDS)}
                  </span>
                )}
              </div>
            </TableCell>
            <TableCell className="py-3 text-right">
              <div className="flex flex-col items-end gap-0.5 whitespace-nowrap tabular-nums">
                <span className="font-medium">{formatMoney(transaction.amount_minor, transaction.currency)}</span>
                {transaction.refunded_minor > 0 ? (
                  <span className="text-muted-foreground text-xs">
                    −{formatMoney(transaction.refunded_minor, transaction.currency)} возвращено
                  </span>
                ) : null}
              </div>
            </TableCell>
            <TableCell className="max-w-56 py-3">
              <MethodCell method={transaction.method} />
            </TableCell>
            <TableCell className="py-3">
              <div className="flex flex-col items-start gap-0.5">
                <StatusBadge status={transaction.status} />
                {transaction.failure_reason ? (
                  <span className="text-muted-foreground text-xs">{transaction.failure_reason}</span>
                ) : null}
                {transaction.status === "refunded" && transaction.refunded_minor < transaction.amount_minor ? (
                  <span className="text-muted-foreground text-xs">Частичный</span>
                ) : null}
              </div>
            </TableCell>
            <TableCell className="py-3">
              {transaction.invoice_url ? (
                <a
                  href={transaction.invoice_url}
                  download
                  className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm text-sm underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <Download className="size-3.5 text-muted-foreground" aria-hidden="true" />
                  <span className="sr-only">Скачать счёт</span>
                  {transaction.number}
                </a>
              ) : (
                <span className="text-muted-foreground">
                  <span aria-hidden="true">—</span>
                  <span className="sr-only">Счёт не выставлен</span>
                </span>
              )}
            </TableCell>
            <TableCell className="py-3 text-right">
              <TransactionActions transaction={transaction} onRefund={onRefund} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const SKELETON_ROWS = Array.from({ length: 8 }, (_, index) => `row-${index}`);

export function TransactionsTableSkeleton() {
  return (
    <Table className={TABLE_CLASS} aria-busy="true" aria-label="Платежи загружаются">
      <Head />
      <TableBody>
        {SKELETON_ROWS.map((key) => (
          <TableRow key={key} className="border-border/60">
            {[...HEADERS, "actions"].map((column) => (
              <TableCell key={column} className="py-4">
                <Skeleton className="h-4 w-full max-w-32" />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
