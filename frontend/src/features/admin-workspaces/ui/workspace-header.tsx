import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

import type { AdminWorkspaceDetail } from "../domain/contract";
import { formatDate, formatFullDateTime, formatNumber, formatRelative, formatUntil } from "../domain/format";
import { StatusBadge } from "./status-badge";
import { WorkspaceActions } from "./workspace-actions";

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm tabular-nums">{children}</dd>
    </div>
  );
}

/** Status and plan, the name and address, the facts at a glance, and what the team can do. */
export function WorkspaceHeader({ workspace: w }: { workspace: AdminWorkspaceDetail }) {
  return (
    <header className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={w.status} />
        <Badge variant="outline">{w.plan.name}</Badge>
        {w.trial_ends_at ? (
          <span className="text-muted-foreground text-sm">
            пробный период закончится {formatUntil(w.trial_ends_at)}
          </span>
        ) : null}
      </div>
      <h1 className="break-words font-semibold text-xl tracking-tight">{w.name}</h1>
      <p className="font-mono text-muted-foreground text-sm">
        /app/w/{w.slug}
        {w.join_domain ? ` · вход по домену ${w.join_domain}` : ""}
      </p>
      <dl className="flex flex-wrap gap-x-8 gap-y-3">
        <Stat label="Владелец">{w.owner?.name ?? "Нет владельца"}</Stat>
        <Stat label="Участники">
          {formatNumber(w.members)}
          {w.pending_invitations ? ` + ${formatNumber(w.pending_invitations)} пригл.` : ""}
        </Stat>
        <Stat label="Места">
          {formatNumber(w.seats_used)} из {formatNumber(w.plan.seats)}
        </Stat>
        <Stat label="Встречи за месяц">{formatNumber(w.meetings_month)}</Stat>
        <Stat label="Минуты за месяц">{formatNumber(w.minutes_month)}</Stat>
        <Stat label="Активность">
          {w.last_active_at ? (
            <time dateTime={w.last_active_at} title={formatFullDateTime(w.last_active_at)}>
              {formatRelative(w.last_active_at)}
            </time>
          ) : (
            "ещё не открывали"
          )}
        </Stat>
        <Stat label="Создано">
          <time dateTime={w.created_at}>{formatDate(w.created_at)}</time>
        </Stat>
      </dl>
      <WorkspaceActions workspace={w} />
    </header>
  );
}
