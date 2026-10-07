"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Progress } from "@/components/ui/progress";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { Usage, WeeklyLimit } from "../../domain/billing-contract";
import { usageResource } from "../../model/settings-resources";
import { SectionState } from "../section-state";
import { SettingsGroup } from "../settings-row";
import { FrontierTopUp } from "./frontier-top-up";
import { useTokenCount } from "./use-token-count";

function LimitMeter({ limit }: { limit: WeeklyLimit }) {
  const t = useTranslations("settingsUsage");
  const format = useFormatter();
  const { amount } = useTokenCount();
  const share = limit.limit_tokens ? Math.min(100, Math.round((limit.used_tokens / limit.limit_tokens) * 100)) : 0;
  const title = t(`tiers.${limit.tier}.title`);
  return (
    <div className="flex flex-col gap-2 py-4">
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-medium text-sm">{title}</span>
        <span className="text-muted-foreground text-sm tabular-nums">
          {t("used", { count: limit.limit_tokens, used: amount(limit.used_tokens), limit: amount(limit.limit_tokens) })}
        </span>
      </div>
      {/* The shared Progress fills from the left; mirrored, it fills from the start in right-to-left too. */}
      <Progress
        value={share}
        aria-label={t("usedLabel", { tier: title, percent: format.number(share / 100, "percent") })}
        className={share >= 90 ? "[&>*]:bg-destructive" : undefined}
      />
      <p className="text-muted-foreground text-xs">{t(`tiers.${limit.tier}.description`)}</p>
    </div>
  );
}

function UsageContent({ usage }: { usage: Usage }) {
  const t = useTranslations("settingsUsage");
  const format = useFormatter();
  const { tokens } = useTokenCount();
  return (
    <div className="flex flex-col gap-6">
      <p className="text-muted-foreground text-sm">
        {/* Limits reset at a fixed UTC moment; the format names its time zone, the one next-intl formats in. */}
        {t("resets", { date: format.dateTime(new Date(usage.resets_at), "weekdayTime") })}
      </p>
      <SettingsGroup title={t("thisWeek")}>
        {usage.limits.map((limit) => (
          <LimitMeter key={limit.tier} limit={limit} />
        ))}
      </SettingsGroup>
      <FrontierTopUp balance={usage.frontier.extra_tokens} packs={usage.frontier.packs} />
      {usage.frontier.models.length > 0 ? (
        <SettingsGroup title={t("frontierThisWeek")}>
          {usage.frontier.models.map((model) => (
            <div key={model.model_id} className="flex items-baseline justify-between gap-4 py-3 text-sm">
              <span>
                {model.name} <span className="text-muted-foreground">· {model.provider}</span>
              </span>
              <span className="text-muted-foreground tabular-nums">{tokens(model.used_tokens)}</span>
            </div>
          ))}
        </SettingsGroup>
      ) : null}
    </div>
  );
}

export function UsageSection() {
  const state = usePollingResource(usageResource);
  return (
    <SectionState state={state} onRetry={() => void usageResource.refresh()}>
      {(usage) => <UsageContent usage={usage} />}
    </SectionState>
  );
}
