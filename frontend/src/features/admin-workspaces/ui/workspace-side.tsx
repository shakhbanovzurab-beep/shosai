import type { ReactNode } from "react";

import { Lock } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { AdminWorkspaceDetail } from "../domain/contract";
import { formatBytes, formatDate, formatMoney, formatNumber, formatUntil, plural } from "../domain/format";
import { SHARE_LEVEL_LABEL, STATUS_LABEL } from "../domain/labels";

function Facts({ items }: { items: [label: string, value: ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words text-right tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function billing(w: AdminWorkspaceDetail) {
  if (w.trial_ends_at) return `Пробный период, до ${formatDate(w.trial_ends_at)} (${formatUntil(w.trial_ends_at)})`;
  return w.status === "suspended" ? "Списывается, доступ приостановлен" : STATUS_LABEL[w.status];
}

/** Plan and billing, how much is inside (counts only), the access rules, and the teams. */
export function WorkspaceSide({ workspace: w }: { workspace: AdminWorkspaceDetail }) {
  const { content: c } = w;
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Тариф и оплата</CardTitle>
        </CardHeader>
        <CardContent>
          <Facts
            items={[
              ["Тариф", w.plan.name],
              ["Места", `${formatNumber(w.seats_used)} из ${formatNumber(w.plan.seats)}`],
              ["За место", formatMoney(w.plan.price_per_seat_cents, w.plan.currency)],
              ["В месяц", formatMoney(w.monthly_cents, w.plan.currency)],
              ["Продление", formatDate(w.plan.renews_at)],
              ["Оплата", billing(w)],
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Содержимое</CardTitle>
          <CardDescription>Только счётчики: что внутри, видят лишь участники.</CardDescription>
        </CardHeader>
        <CardContent>
          <Facts
            items={[
              ["Общие встречи", formatNumber(c.shared_meetings)],
              ["Решения", formatNumber(c.decisions)],
              ["Открытые задачи", formatNumber(c.open_tasks)],
              ["Проекты", `${formatNumber(c.projects)}, в работе ${formatNumber(c.active_projects)}`],
              ["Файлы", formatNumber(c.files)],
              ["Подключённые источники", formatNumber(c.sources)],
              ["Объём знаний", formatBytes(c.knowledge_bytes)],
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Доступ</CardTitle>
        </CardHeader>
        <CardContent>
          <Facts
            items={[
              ["Вход по домену", w.join_domain ?? "Выключен"],
              ["Встречи по умолчанию", SHARE_LEVEL_LABEL[w.sharing.default_level]],
              ["Расшифровки", w.sharing.share_transcripts ? "Вместе со сводкой" : "Только сводка"],
              ["Приглашают", w.sharing.members_can_invite ? "Все участники" : "Только администраторы"],
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Команды</CardTitle>
          <CardDescription>
            {w.teams.length ? plural(w.teams.length, ["команда", "команды", "команд"]) : "Команд нет"}
          </CardDescription>
        </CardHeader>
        {w.teams.length ? (
          <CardContent>
            <ul className="flex flex-col gap-1.5 text-sm">
              {w.teams.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-3">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className="truncate">{t.name}</span>
                    {t.private ? (
                      <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-label="Закрытая" />
                    ) : null}
                  </span>
                  <span className="shrink-0 text-muted-foreground tabular-nums">{formatNumber(t.members)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        ) : null}
      </Card>
    </div>
  );
}
