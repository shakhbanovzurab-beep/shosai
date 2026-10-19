"use client";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/lib/navigation";

import { worstTone } from "../../domain/usage-meters";
import { useSettingsDialog } from "../../model/dialog-store";
import { useUsageOverview } from "../../model/usage-overview";
import { UsageMeterRow } from "./usage-meter-row";

/**
 * Всё, что считается по плану, на одной карточке: токены недели, минуты встреч месяца, хранилище и файлы Leo.
 * Единственное место с лимитами (billing, «one usage view»): страница тарифов показывает планы, а не расход.
 * Кнопка к тарифам становится заметной, только когда что-то исчерпано, — о лимите говорят там, где он мешает.
 */
export function UsageOverview() {
  const t = useTranslations("settingsUsage");
  const { loading, rows, plan, unlimitedMinutesPlan } = useUsageOverview();
  const close = useSettingsDialog((s) => s.close);
  if (rows.length === 0) return loading ? <Skeleton className="h-44 rounded-xl" /> : null;
  const full = worstTone(rows.map((row) => row.tone)) === "full";
  return (
    <Card size="sm" aria-busy={loading || undefined}>
      <CardHeader>
        {/* По плану, а не «Использование»: в настройках так уже назван сам раздел. */}
        <CardTitle>{plan ? t("overview.plan", { plan }) : t("overview.title")}</CardTitle>
        <CardAction>
          <Button asChild size="sm" variant={full ? "default" : "outline"}>
            <Link href="/app/upgrade" onClick={close}>
              {t("overview.seePlans")}
            </Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
        {rows.map((row) => (
          <UsageMeterRow key={row.kind} row={row} unlimitedMinutesPlan={unlimitedMinutesPlan} />
        ))}
      </CardContent>
    </Card>
  );
}
