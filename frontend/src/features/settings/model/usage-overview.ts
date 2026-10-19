"use client";

import type { StorageStanding } from "@/features/file-manager/domain/contract";
import { useStorage } from "@/features/file-manager/model/storage-resource";
import type { PlansResponse } from "@/features/upgrade/domain/contract";
import { usePlans } from "@/features/upgrade/model/plans-resource";
import { usePollingResource } from "@/hooks/use-polling-resource";
import type { ResourceState } from "@/lib/polling-resource";

import type { Usage } from "../domain/billing-contract";
import { frontierStanding, type MeterTone, meterStanding, type UsageKind } from "../domain/usage-meters";
import { usageResource } from "./settings-resources";

/*
 * Единый вид использования собирает три источника: токены недели (billing), минуты встреч месяца (billing,
 * через Upgrade) и хранилище с файлами Leo (files). Запросы идут параллельно; строки источника, который не
 * ответил, просто не показываются.
 */

export type UsageRow = {
  kind: UsageKind;
  used: number;
  /** null — без лимита. */
  limit: number | null;
  share: number | null;
  tone: MeterTone;
  /** Когда лимит сбросится; у хранилища сброса нет. */
  resetsAt: string | null;
  /** Купленные frontier-токены, тратятся после недельного лимита. */
  extraTokens: number;
};

export type UsageSources = { usage: Usage | null; plans: PlansResponse | null; storage: StorageStanding | null };

/** Строки по порядку: токены, минуты, хранилище, файлы Leo; то, что в план не входит (лимит 0), пропускается. */
export function usageRows({ usage, plans, storage }: UsageSources): UsageRow[] {
  const rows: UsageRow[] = [];
  const add = (row: Omit<UsageRow, "share" | "tone">, standing = meterStanding(row.used, row.limit)) => {
    if (row.limit !== 0) rows.push({ ...row, ...standing });
  };
  const extraTokens = usage?.frontier.extra_tokens ?? 0;
  for (const { tier, used_tokens: used, limit_tokens: limit } of usage?.limits ?? []) {
    const row = { kind: tier, used, limit, resetsAt: usage?.resets_at ?? null, extraTokens };
    add(row, tier === "frontier" ? frontierStanding(used, limit, extraTokens) : undefined);
  }
  if (plans) {
    const { used_minutes: used, limit_minutes: limit, resets_at: resetsAt } = plans.usage;
    add({ kind: "minutes", used, limit, resetsAt, extraTokens: 0 });
  }
  if (storage) {
    add({ kind: "storage", used: storage.used_bytes, limit: storage.limit_bytes, resetsAt: null, extraTokens: 0 });
    const leo = { used: storage.leo_used_bytes, limit: storage.leo_limit_bytes };
    add({ kind: "knowledge", ...leo, resetsAt: null, extraTokens: 0 });
  }
  return rows;
}

const readyData = <T>(state: ResourceState<T>): T | null => (state.status === "ready" ? state.data : null);

/** Строки вида, план, по которому они считаются, и план с безлимитными минутами — для подсказки. */
export function useUsageOverview() {
  const usage = usePollingResource(usageResource);
  const plans = usePlans();
  const storage = useStorage();
  const catalogue = readyData(plans);
  return {
    loading: [usage, plans, storage].some((state) => state.status === "loading"),
    rows: usageRows({ usage: readyData(usage), plans: catalogue, storage: readyData(storage) }),
    plan: catalogue?.plans.find((p) => p.id === catalogue.effective_plan_id)?.name ?? null,
    unlimitedMinutesPlan:
      catalogue?.plans.find((p) => p.entitlements.meeting_minutes_per_month === null && p.price !== null)?.name ?? null,
  };
}
