"use client";

import { useState } from "react";

import { useSearchParams } from "next/navigation";

import { ReceiptText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { pluralizeRu } from "@/lib/plural";

import type { Transaction, TransactionsQuery } from "../domain/contract";
import { formatInteger } from "../domain/format";
import { DEFAULT_PERIOD, parseTransactionsQuery, transactionsSearch } from "../domain/query";
import { transactionsResource } from "../model/billing-store";
import { BillingError } from "./billing-state";
import { RefundDialog } from "./refund-dialog";
import { TransactionsFilters } from "./transactions-filters";
import { TransactionsPagination } from "./transactions-pagination";
import { TransactionsTable, TransactionsTableSkeleton } from "./transactions-table";

const PAYMENT_WORDS = ["платёж", "платежа", "платежей"] as const;

function TransactionsEmpty({ filtered, onReset }: { filtered: boolean; onReset: () => void }) {
  return (
    <Empty className="mx-4 border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <ReceiptText />
        </EmptyMedia>
        <EmptyTitle>Платежей не найдено</EmptyTitle>
        <EmptyDescription>
          {filtered ? "Под выбранные фильтры платежей нет." : "Клиенты ещё ничего не оплачивали."}
        </EmptyDescription>
      </EmptyHeader>
      {filtered ? (
        <EmptyContent>
          <Button variant="outline" size="sm" onClick={onReset}>
            Сбросить фильтры
          </Button>
        </EmptyContent>
      ) : null}
    </Empty>
  );
}

/** Every customer payment with status, period and currency filters kept in the URL, paged on the server. */
export function TransactionsCard() {
  const searchParams = useSearchParams();
  const query = parseTransactionsQuery(searchParams);
  const search = transactionsSearch(query);
  const resource = transactionsResource(search);
  const state = usePollingResource(resource);
  const [refundTarget, setRefundTarget] = useState<Transaction | null>(null);

  // The native history API keeps useSearchParams in sync without a server round trip.
  const navigate = (next: TransactionsQuery) =>
    window.history.replaceState(null, "", `${window.location.pathname}${transactionsSearch(next)}`);
  const filtered = query.status !== undefined || query.currency !== undefined || query.period !== DEFAULT_PERIOD;

  return (
    <Card>
      <CardHeader className="border-b has-data-[slot=card-action]:grid-cols-1 md:has-data-[slot=card-action]:grid-cols-[1fr_auto]">
        <CardTitle className="text-xl leading-none">Платежи</CardTitle>
        <CardDescription aria-live="polite">
          {state.status === "ready"
            ? `${formatInteger(state.data.total)} ${pluralizeRu(state.data.total, PAYMENT_WORDS)} от клиентов платформы`
            : "Все платежи клиентов платформы"}
        </CardDescription>
        <CardAction className="col-start-1 row-start-auto flex w-full flex-wrap gap-2 justify-self-stretch md:col-start-2 md:row-span-2 md:row-start-1 md:w-auto md:justify-end md:justify-self-end">
          <TransactionsFilters query={query} onChange={navigate} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-0">
        {state.status === "loading" ? <TransactionsTableSkeleton /> : null}
        {state.status === "error" ? (
          <div className="px-4">
            <BillingError
              title="Не удалось загрузить платежи"
              message={state.message}
              onRetry={() => void resource.refresh()}
            />
          </div>
        ) : null}
        {state.status === "ready" && state.data.items.length === 0 ? (
          <TransactionsEmpty filtered={filtered} onReset={() => navigate({ period: DEFAULT_PERIOD, page: 1 })} />
        ) : null}
        {state.status === "ready" && state.data.items.length > 0 ? (
          <>
            <TransactionsTable items={state.data.items} busy={state.refreshing} onRefund={setRefundTarget} />
            <TransactionsPagination
              page={state.data.page}
              pageCount={state.data.total_pages}
              total={state.data.total}
              disabled={state.refreshing}
              onPage={(page) => navigate({ ...query, page })}
            />
          </>
        ) : null}
      </CardContent>
      <RefundDialog transaction={refundTarget} search={search} onClose={() => setRefundTarget(null)} />
    </Card>
  );
}

export function TransactionsCardSkeleton() {
  return (
    <Card aria-busy="true">
      <CardHeader className="border-b">
        <CardTitle className="text-xl leading-none">Платежи</CardTitle>
        <CardDescription>Загружаем платежи…</CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <TransactionsTableSkeleton />
      </CardContent>
    </Card>
  );
}
