import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { AdminWorkspace } from "../domain/contract";
import { formatMoney, formatNumber } from "../domain/format";
import { totals } from "../domain/list";

function Kpi({ title, value, footer }: { title: string; value: string; footer: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-normal text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="text-2xl tabular-nums leading-none tracking-tight">{value}</div>
        <div className="text-muted-foreground text-xs">{footer}</div>
      </CardContent>
    </Card>
  );
}

/** How many workspaces, how full they are, what they bring in, how much they're used, and what needs a look. */
export function WorkspacesKpis({ rows }: { rows: AdminWorkspace[] }) {
  const sum = totals(rows);
  const currency = rows[0]?.plan.currency ?? "USD";
  const share = sum.seats ? Math.round((sum.used / sum.seats) * 100) : 0;
  return (
    <section
      aria-label="Сводка по пространствам"
      className="overflow-hidden rounded-xl bg-card shadow-xs ring-1 ring-foreground/10"
    >
      <div className="grid divide-y *:data-[slot=card]:rounded-none *:data-[slot=card]:ring-0 md:grid-cols-2 md:divide-x md:divide-y-0 xl:grid-cols-5">
        <Kpi title="Пространства" value={formatNumber(sum.count)} footer={`работают: ${formatNumber(sum.active)}`} />
        <Kpi
          title="Места"
          value={`${formatNumber(sum.used)} / ${formatNumber(sum.seats)}`}
          footer={`занято ${share} % оплаченных мест`}
        />
        <Kpi title="Выручка в месяц" value={formatMoney(sum.monthly, currency)} footer="без приостановленных" />
        <Kpi title="Минуты встреч" value={formatNumber(sum.minutes)} footer="за текущий месяц" />
        <Kpi
          title="Требуют внимания"
          value={formatNumber(sum.attention)}
          footer={sum.attention > 0 ? "оплата, места, приостановка или тишина" : "всё в порядке"}
        />
      </div>
    </section>
  );
}
