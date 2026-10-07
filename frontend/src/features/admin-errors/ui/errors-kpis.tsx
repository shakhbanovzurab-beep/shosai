import type { ReactNode } from "react";

import { cn } from "cn";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { ErrorsKpis as Kpis } from "../domain/contract";
import { formatNumber, formatPercent, percentChange } from "../domain/format";
import { SourceIcon } from "./issue-meta";

const deltaFormat = new Intl.NumberFormat("ru-RU", {
  style: "percent",
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});
const pointsFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2, signDisplay: "exceptZero" });

/** A change badge; `goodWhenUp` says which direction is an improvement. */
function Delta({ value, label, goodWhenUp }: { value: number | null; label: string; goodWhenUp: boolean }) {
  if (value === null || Math.abs(value) < 0.0005)
    return (
      <Badge variant="secondary">
        <Minus aria-hidden="true" />
        без изменений
      </Badge>
    );
  const up = value > 0;
  const good = up === goodWhenUp;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <Badge
      className={cn(
        good
          ? "bg-green-500/10 text-green-700 dark:bg-green-500/15 dark:text-green-300"
          : "bg-red-500/10 text-red-700 dark:bg-red-500/15 dark:text-red-300",
      )}
    >
      <Icon aria-hidden="true" />
      <span className="sr-only">{up ? "рост" : "снижение"} </span>
      {label}
    </Badge>
  );
}

function Kpi({ title, value, delta, footer }: { title: ReactNode; value: string; delta: ReactNode; footer: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5 font-normal text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <div className="text-2xl tabular-nums leading-none tracking-tight">{value}</div>
          {delta}
        </div>
        <div className="text-muted-foreground text-xs">{footer}</div>
      </CardContent>
    </Card>
  );
}

function countDelta(current: number, previous: number) {
  const change = percentChange(current, previous);
  return <Delta value={change} label={change === null ? "" : deltaFormat.format(change)} goodWhenUp={false} />;
}

export function ErrorsKpis({ kpis }: { kpis: Kpis }) {
  return (
    <section
      aria-label="Показатели за 24 часа"
      className="overflow-hidden rounded-xl bg-card shadow-xs ring-1 ring-foreground/10"
    >
      <div className="grid divide-y *:data-[slot=card]:rounded-none *:data-[slot=card]:ring-0 md:grid-cols-2 md:divide-x md:divide-y-0 xl:grid-cols-5">
        <Kpi
          title="Новые ошибки"
          value={formatNumber(kpis.new_issues_24h)}
          delta={countDelta(kpis.new_issues_24h, kpis.new_issues_prev_24h)}
          footer={`за 24 ч · было ${formatNumber(kpis.new_issues_prev_24h)}`}
        />
        <Kpi
          title="События"
          value={formatNumber(kpis.events_24h)}
          delta={countDelta(kpis.events_24h, kpis.events_prev_24h)}
          footer={`за 24 ч · было ${formatNumber(kpis.events_prev_24h)}`}
        />
        <Kpi
          title="Затронуто пользователей"
          value={formatNumber(kpis.affected_users_24h)}
          delta={countDelta(kpis.affected_users_24h, kpis.affected_users_prev_24h)}
          footer={`за 24 ч · было ${formatNumber(kpis.affected_users_prev_24h)}`}
        />
        {kpis.crash_free.map((client) => {
          const points = (client.rate - client.previous_rate) * 100;
          return (
            <Kpi
              key={client.source}
              title={
                <>
                  <SourceIcon source={client.source} className="size-3.5 text-muted-foreground" />
                  Сессии без сбоев · {client.source === "macos" ? "macOS" : "Windows"}
                </>
              }
              value={formatPercent(client.rate)}
              delta={<Delta value={points / 100} label={`${pointsFormat.format(points)} п.п.`} goodWhenUp />}
              footer={`${formatNumber(client.sessions)} сессий за 24 ч`}
            />
          );
        })}
      </div>
    </section>
  );
}
