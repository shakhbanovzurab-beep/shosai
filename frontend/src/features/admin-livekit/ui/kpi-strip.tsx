import type { LucideIcon } from "lucide-react";
import { ArrowDownToLine, ArrowUpFromLine, AudioLines, CircleDot, DoorOpen, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { LiveKitStats } from "../domain/contract";
import { formatInteger, formatMbps, orNoData } from "../domain/format";

type Kpi = { label: string; value: string; hint: string; icon: LucideIcon };

const NO_METRICS = "Нет данных Prometheus";

function kpis(stats: LiveKitStats): Kpi[] {
  return [
    { label: "Активные комнаты", value: formatInteger(stats.active_rooms), hint: "Идущие встречи", icon: DoorOpen },
    { label: "Участники онлайн", value: formatInteger(stats.participants), hint: "Во всех комнатах", icon: Users },
    {
      label: "Опубликованные треки",
      value: orNoData(stats.published_tracks, formatInteger),
      hint: stats.published_tracks === null ? NO_METRICS : "Аудио, видео и экран",
      icon: AudioLines,
    },
    {
      label: "Входящий трафик",
      value: orNoData(stats.bandwidth_in_mbps, formatMbps),
      hint: stats.bandwidth_in_mbps === null ? NO_METRICS : "От участников",
      icon: ArrowDownToLine,
    },
    {
      label: "Исходящий трафик",
      value: orNoData(stats.bandwidth_out_mbps, formatMbps),
      hint: stats.bandwidth_out_mbps === null ? NO_METRICS : "К участникам",
      icon: ArrowUpFromLine,
    },
    { label: "Запись и экспорт", value: formatInteger(stats.active_egress), hint: "Активные задания", icon: CircleDot },
  ];
}

export function KpiStrip({ stats }: { stats: LiveKitStats }) {
  return (
    <section
      aria-label="Ключевые показатели"
      className="overflow-hidden rounded-xl bg-card shadow-xs ring-1 ring-foreground/10"
    >
      <div className="grid divide-y *:data-[slot=card]:rounded-none *:data-[slot=card]:ring-0 sm:grid-cols-2 sm:divide-x md:grid-cols-3 xl:grid-cols-6 xl:divide-y-0">
        {kpis(stats).map(({ label, value, hint, icon: Icon }) => (
          <Card key={label}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-normal text-muted-foreground text-sm">
                <Icon aria-hidden="true" className="size-4" />
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1">
              <div className="text-2xl tabular-nums leading-none tracking-tight">{value}</div>
              <div className="text-muted-foreground text-xs">{hint}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
