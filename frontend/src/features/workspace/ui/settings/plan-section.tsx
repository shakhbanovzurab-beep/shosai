"use client";

import Link from "next/link";

import { useFormatter, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useNow } from "@/hooks/use-now";

import { IDLE_DAYS, isIdle, lastActive, moneyAmount } from "../../domain/format";
import { seatUsage } from "../../domain/people";
import { useResources, useUsage, useWorkspace } from "../../model/use-workspace";
import { PersonLabel } from "../shared/people";
import { useWorkspaceDates } from "../shared/use-dates";
import { SettingsCard } from "./setting-row";

function UsageTable() {
  const t = useTranslations("workspaceSettings");
  const shared = useTranslations("workspace");
  const common = useTranslations("common");
  const format = useFormatter();
  const dates = useWorkspaceDates();
  const { state } = useWorkspace();
  const usage = useUsage();
  const resources = useResources();
  const now = useNow();
  if (usage.status === "loading" || now === null) return <Skeleton className="h-48 rounded-lg" />;
  if (usage.status === "error")
    return (
      <p className="text-muted-foreground text-sm">
        {t("plan.usageFailed")}{" "}
        <Button variant="link" className="h-auto p-0" onClick={() => void resources.usage.refresh()}>
          {common("actions.retry")}
        </Button>
      </p>
    );
  const byMember = new Map(usage.data.members.map((u) => [u.member_id, u]));
  const idle = state.members.filter((m) => isIdle(m.last_active_at, now));
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium text-sm">
          {t("plan.usageIn", {
            // The month starts at midnight UTC, the formatter's own zone.
            month: format.dateTime(new Date(usage.data.month_start), { month: "long", year: "numeric" }),
          })}
        </h3>
        {idle.length > 0 ? (
          <span className="text-muted-foreground text-xs">
            {t("plan.idle", { count: idle.length, days: IDLE_DAYS })}
          </span>
        ) : null}
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("plan.member")}</TableHead>
              <TableHead className="text-end">{t("plan.meetings")}</TableHead>
              <TableHead className="text-end">{t("plan.minutes")}</TableHead>
              <TableHead className="hidden sm:table-cell">{t("plan.lastActive")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.members.map((member) => {
              const row = byMember.get(member.id);
              return (
                <TableRow key={member.id}>
                  <TableCell className="max-w-48">
                    <PersonLabel
                      name={member.name}
                      label={member.id === state.me_id ? shared("people.nameYou", { name: member.name }) : undefined}
                    />
                  </TableCell>
                  <TableCell className="text-end tabular-nums">{format.number(row?.meetings ?? 0)}</TableCell>
                  <TableCell className="text-end tabular-nums">{format.number(row?.minutes ?? 0)}</TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <span className="inline-flex items-center gap-2 text-muted-foreground">
                      {dates.lastActive(lastActive(member.last_active_at, now))}
                      {isIdle(member.last_active_at, now) ? (
                        <Badge variant="outline">{t("plan.inactive")}</Badge>
                      ) : null}
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/** What the workspace pays for and how it's used, for admins; changing seats is the owner's. */
export function PlanSection() {
  const t = useTranslations("workspaceSettings");
  const format = useFormatter();
  const { state, can } = useWorkspace();
  const { plan } = state.workspace;
  const seats = seatUsage(state);
  const money = (cents: number) => {
    const { value, digits } = moneyAmount(cents);
    return format.number(value, {
      style: "currency",
      currency: plan.currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  };
  return (
    <SettingsCard id="plan" title={t("plan.title")} description={t("plan.description")}>
      <div className="flex flex-col gap-4 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-2 font-medium">
            {t("plan.name", { plan: plan.name })}
            <Badge variant="secondary">
              {t("plan.seats", { taken: seats.members + seats.pending, total: plan.seats })}
            </Badge>
          </span>
          <span className="text-muted-foreground text-sm">
            {t("plan.price", {
              perSeat: money(plan.price_per_seat_cents),
              total: money(plan.price_per_seat_cents * plan.seats),
              // Renewal is a day, starting at midnight UTC: formatted in UTC, the formatter's own zone.
              renews: format.dateTime(new Date(plan.renews_at), "medium"),
            })}
          </span>
        </div>
        {can.manageBilling ? (
          <Button asChild variant="outline">
            <Link href="/app/upgrade">{t("plan.change")}</Link>
          </Button>
        ) : (
          <span className="text-muted-foreground text-xs">{t("plan.ownerOnly")}</span>
        )}
      </div>
      <div className="pt-4">
        <UsageTable />
      </div>
    </SettingsCard>
  );
}
