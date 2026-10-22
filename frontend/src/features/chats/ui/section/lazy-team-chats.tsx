"use client";

import { lazy, Suspense } from "react";

import { useTranslations } from "use-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { SettingsCard } from "@/features/workspace/ui/settings/setting-row";

/*
 * «Командные чаты» — своим чанком: маршрут настроек пространства растёт меньше чем на килобайт (план §4.4), а
 * раздел грузится, когда страница открыта. До того — его шапка и строки-заглушки той же высоты, без сдвига.
 */

const TeamChatsSection = lazy(() =>
  import("./team-chats-section").then((module) => ({ default: module.TeamChatsSection })),
);

function TeamChatsSkeleton() {
  const t = useTranslations("chats");
  return (
    <SettingsCard id="chats" title={t("section.title")} description={t("section.description")}>
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-center gap-3 py-3" aria-hidden="true">
          <Skeleton className="size-8 rounded-lg" />
          <div className="flex flex-1 flex-col gap-1.5">
            <Skeleton className="h-3.5 w-40" />
            <Skeleton className="h-3 w-64 max-w-full" />
          </div>
        </div>
      ))}
    </SettingsCard>
  );
}

export function LazyTeamChatsSection() {
  return (
    <Suspense fallback={<TeamChatsSkeleton />}>
      <TeamChatsSection />
    </Suspense>
  );
}
