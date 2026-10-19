"use client";

import { useTranslations } from "use-intl";

import { usePollingResource } from "@/hooks/use-polling-resource";

import type { Usage } from "../../domain/billing-contract";
import { usageResource } from "../../model/settings-resources";
import { SectionState } from "../section-state";
import { SettingsGroup } from "../settings-row";
import { FrontierTopUp } from "./frontier-top-up";
import { UsageOverview } from "./usage-overview";
import { useTokenCount } from "./use-token-count";

/** Под общим видом использования — то, что есть только у токенов: купленный запас и frontier-модели недели. */
function UsageContent({ usage }: { usage: Usage }) {
  const t = useTranslations("settingsUsage");
  const { tokens } = useTokenCount();
  return (
    <div className="flex flex-col gap-6">
      <UsageOverview />
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
